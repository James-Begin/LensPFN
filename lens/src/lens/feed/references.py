"""Resolve bibliography metadata using Semantic Scholar and arXiv DOI deposits."""

from difflib import SequenceMatcher
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

API = "https://api.semanticscholar.org/graph/v1/paper/"
FIELDS = "title,authors,year,externalIds,url"
_lock = threading.Lock()
_last_request = 0.0
_retry_after = {}
_datacite_lock = threading.Lock()
_datacite_last = 0.0
_datacite_retry = 0.0
ID_PATTERN = r"(?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?"
USER_AGENT = "LensPFN/0.8.0 (https://github.com/James-Begin/LensPFN)"


def title_key(value):
    return " ".join(re.findall(r"\w+", value.casefold()))


def relevance(details, paper):
    """Prefer title agreement, then author overlap and publication year."""
    wanted = title_key(details["title"] or details["reference"])
    title = SequenceMatcher(None, wanted, title_key(paper["title"])).ratio()
    if not details["title"]:
        words = set(title_key(paper["title"]).split())
        if len(words) >= 3:
            title = max(title, len(words & set(wanted.split())) / len(words))
    reference_authors = set(title_key(details.get("authors", "")).split())
    authors = paper.get("authors") or []
    surnames = {title_key(author).split()[-1] for author in authors if title_key(author)}
    overlap = len(reference_authors & surnames) / max(1, len(surnames))
    year = str(paper.get("year") or paper.get("created", "")[:4])
    year_match = bool(details.get("year") and details["year"] == year)
    return (bool(paper.get("doi_match")), round(title, 3), overlap, year_match)


def _datacite(details):
    """Search public arXiv DOI deposits, including their full abstract metadata."""
    global _datacite_last, _datacite_retry
    words = title_key(details["title"] or details["reference"])[:500]
    if details["title"]:
        query = f'prefix:10.48550 AND titles.title:"{words}"'
    else:
        query = f"prefix:10.48550 AND ({words})"
    if details["doi"]:
        doi = details["doi"].replace("\\", "\\\\").replace('"', '\\"')
        query = f'prefix:10.48550 AND (relatedIdentifiers.relatedIdentifier:"{doi}" OR {query})'
    url = "https://api.datacite.org/dois?" + urlencode(
        {"query": query, "sort": "relevance", "page[size]": 25}
    )
    with _datacite_lock:
        if time.monotonic() < _datacite_retry:
            raise RuntimeError("arXiv DOI metadata lookup is cooling down.")
        time.sleep(max(0, 1.0 - (time.monotonic() - _datacite_last)))
        _datacite_last = time.monotonic()
        try:
            with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=15) as response:
                rows = json.load(response).get("data", [])
        except HTTPError as error:
            if error.code == 429:
                delay = (error.headers or {}).get("Retry-After", "60")
                _datacite_retry = time.monotonic() + max(60, int(delay) if delay.isdigit() else 60)
            raise
    papers = []
    for row in rows:
        doi = row.get("id", "")
        if not doi.lower().startswith("10.48550/arxiv."):
            continue
        pid = doi[len("10.48550/arxiv.") :]
        if not re.fullmatch(ID_PATTERN, pid):
            continue
        pid = re.sub(r"v\d+$", "", pid)
        data = row.get("attributes") or {}
        title = next((t.get("title", "") for t in data.get("titles", []) if t.get("title")), "")
        if not title:
            continue
        authors = [
            " ".join(filter(None, [a.get("givenName"), a.get("familyName")])) or a.get("name", "")
            for a in data.get("creators", [])
        ]
        abstract = next(
            (
                d.get("description", "")
                for d in data.get("descriptions", [])
                if d.get("descriptionType") == "Abstract"
            ),
            "",
        )
        categories = list(
            dict.fromkeys(
                code
                for s in data.get("subjects", [])
                for code in re.findall(r"\(([a-z-]+(?:\.[A-Z]{2})?)\)", s.get("subject", ""))
            )
        )
        dates = [
            d["date"][:10]
            for d in data.get("dates", [])
            if d.get("dateType") == "Submitted" and d.get("date") and len(d["date"]) >= 10
        ]
        created = min(dates) if dates else str(data.get("publicationYear") or "") + "-01-01"
        try:
            date.fromisoformat(created)
        except ValueError:
            continue
        related = [
            r.get("relatedIdentifier", "").casefold() for r in data.get("relatedIdentifiers", [])
        ]
        papers.append(
            {
                "id": pid,
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "year": data.get("publicationYear"),
                "created": created,
                "categories": categories,
                "primary": categories[0] if categories else "",
                "url": "https://arxiv.org/abs/" + pid,
                "doi": doi,
                "source": "datacite",
                "doi_match": bool(details["doi"] and details["doi"].casefold() in related),
            }
        )
    return papers


def _get(path):
    global _last_request
    with _lock:
        scope = "search" if path.startswith("search?") else "identifier"
        if time.monotonic() < _retry_after.get(scope, 0):
            raise RuntimeError(
                "Reference lookup is busy. Try again shortly or link an arXiv URL manually."
            )
        time.sleep(max(0, 1.0 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        headers = {"User-Agent": USER_AGENT}
        if os.environ.get("S2_API_KEY"):
            headers["x-api-key"] = os.environ["S2_API_KEY"]
        try:
            with urlopen(Request(API + path, headers=headers), timeout=15) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 429:
                delay = (error.headers or {}).get("Retry-After", "60")
                _retry_after[scope] = time.monotonic() + max(
                    60, int(delay) if delay.isdigit() else 60
                )
                raise RuntimeError(
                    "Reference lookup is busy. Try again shortly or link an arXiv URL manually."
                ) from None
            if error.code == 404:
                return None
            raise


def resolve(details, cache: Path, local=()):
    title, reference, doi = details["title"], details["reference"], details["doi"]
    wanted = title_key(title)
    # Resolve a known title immediately; author/year details break duplicate ties.
    exact = {p["id"]: p for p in local if wanted and title_key(p["title"]) == wanted}
    if exact:
        return {
            "state": "resolved",
            "candidates": sorted(exact.values(), key=lambda p: relevance(details, p), reverse=True)[
                :3
            ],
            "warning": "Found the closest arXiv version.",
        }
    # Bypass older negative entries that never tried the DOI-deposit fallback.
    key = hashlib.sha256(("auto-v3:" + json.dumps(details, sort_keys=True)).encode()).hexdigest()
    path = cache / (key + ".json")
    if path.exists() and time.time() - path.stat().st_mtime < 86400:
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
    candidates = []
    record = None
    if doi:
        try:
            record = _get(quote("DOI:" + doi, safe="") + "?" + urlencode({"fields": FIELDS}))
        except (OSError, RuntimeError, ValueError):
            pass
    if record and (record.get("externalIds") or {}).get("ArXiv"):
        records = [record]
        state = "resolved"
    else:
        query = title or reference
        if len(query) < 12:
            return {
                "state": "unresolved",
                "candidates": [],
                "warning": "Not enough reference text to identify this paper.",
            }
        try:
            records = (
                _get("search?" + urlencode({"query": query[:500], "limit": 10, "fields": FIELDS}))
                or {}
            ).get("data", [])
        except (OSError, RuntimeError, ValueError):
            records = []
        state = "candidate"
    for row in records:
        pid = (row.get("externalIds") or {}).get("ArXiv", "")
        if not isinstance(pid, str) or not re.fullmatch(ID_PATTERN, pid):
            continue
        candidate_title = row.get("title") or ""
        if (
            state != "resolved"
            and wanted
            and SequenceMatcher(None, wanted, title_key(candidate_title)).ratio() < 0.8
        ):
            continue
        candidates.append(
            {
                "id": re.sub(r"v\d+$", "", pid),
                "title": candidate_title,
                "authors": [a.get("name", "") for a in row.get("authors", [])],
                "year": row.get("year"),
                "url": "https://arxiv.org/abs/" + pid,
            }
        )
    if not candidates:
        try:
            fallback = _datacite(details)
            for paper in fallback:
                if paper["doi_match"] or relevance(details, paper)[1] >= 0.8:
                    candidates.append(paper)
        except (OSError, RuntimeError, ValueError):
            return {
                "state": "unavailable",
                "candidates": [],
                "warning": "Paper lookup services are temporarily unavailable. Reference details are still available; try hovering again shortly.",
            }
    candidates.sort(key=lambda p: relevance(details, p), reverse=True)
    result = {
        "state": "resolved" if candidates else "unresolved",
        "candidates": candidates,
        "warning": (
            "Found an arXiv version from the DOI."
            if state == "resolved" and candidates
            else "Found the closest arXiv version."
            if candidates
            else "No arXiv version found. Search by title or paste an arXiv URL if you find one."
        ),
    }
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    return result
