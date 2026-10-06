"""Polite arXiv OAI-PMH harvester for Lens Feed.

arXiv API terms (https://info.arxiv.org/help/api/tou.html): metadata is CC0; at most one
request every three seconds over a single connection; link users to abstract pages
and do not host PDFs. Raw responses are cached on disk so re-runs do not re-request.
"""

from __future__ import annotations

from datetime import date, timedelta
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

OAI = "https://oaipmh.arxiv.org/oai"
USER_AGENT = "LensPFN/0.8.0 (https://github.com/James-Begin/LensPFN)"
MIN_INTERVAL = 3.5  # seconds between requests (arXiv asks for >= 3)
NS = {"oai": "http://www.openarchives.org/OAI/2.0/", "ax": "http://arxiv.org/OAI/arXiv/"}
TOP_LEVEL_SETS = {"cs", "math", "stat", "eess", "econ", "q-bio", "q-fin", "physics"}

NEW_GRACE_DAYS = 14

_last_request = 0.0


class _AbstractMetadata(HTMLParser):
    """Read citation metadata from an arXiv abstract page when OAI GetRecord fails."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, list[str]] = {}
        self.subjects: list[str] = []
        self._in_subjects = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name", "").startswith("citation_"):
            self.meta.setdefault(a["name"], []).append(a.get("content", ""))
        if tag == "td" and "subjects" in a.get("class", "").split():
            self._in_subjects = True

    def handle_endtag(self, tag):
        if tag == "td":
            self._in_subjects = False

    def handle_data(self, data):
        if self._in_subjects:
            self.subjects.append(data)


def _abstract_record(arxiv_id: str, cache: Path) -> dict:
    """Fetch public abstract-page metadata with the same polite request spacing."""
    global _last_request
    path = cache / f"abs-{arxiv_id.replace('/', '-')}.html"
    if path.exists():
        html = path.read_text(encoding="utf-8")
    else:
        wait = MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        request = urllib.request.Request(
            f"https://arxiv.org/abs/{arxiv_id}", headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            html = response.read().decode("utf-8")
        cache.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
    parser = _AbstractMetadata()
    parser.feed(html)
    fields = parser.meta
    get = lambda name: _clean(fields.get(name, [""])[0])
    found = get("citation_arxiv_id")
    if found != arxiv_id or not get("citation_title") or not get("citation_abstract"):
        raise ValueError(f"arXiv paper {arxiv_id!r} has incomplete metadata")
    categories = list(
        dict.fromkeys(re.findall(r"\(([a-z-]+(?:\.[A-Z]{2})?)\)", " ".join(parser.subjects)))
    )
    created = get("citation_date").replace("/", "-")
    updated = get("citation_online_date").replace("/", "-")
    return {
        "id": found,
        "title": get("citation_title"),
        "abstract": get("citation_abstract"),
        "authors": [a.removeprefix(" ") for a in fields.get("citation_author", [])],
        "categories": categories,
        "primary": categories[0] if categories else "",
        "created": created,
        "updated": updated,
        "doi": get("citation_doi"),
        "license": "",
        "url": f"https://arxiv.org/abs/{found}",
    }


def _get(params: dict, cache: Path, *, retries: int = 4) -> str:
    """Fetch one OAI page, served from cache when possible, rate-limited otherwise."""
    global _last_request
    key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:24]
    path = cache / f"{key}.xml"
    if path.exists():
        return path.read_text(encoding="utf-8")
    url = f"{OAI}?{urllib.parse.urlencode(params)}"
    for attempt in range(retries):
        wait = MIN_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as response:
                text = response.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503) and attempt < retries - 1:
                retry_after = exc.headers.get("Retry-After")
                time.sleep(
                    int(retry_after)
                    if retry_after and retry_after.isdigit()
                    else 30 * (attempt + 1)
                )
                continue
            raise
    cache.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse(record: ET.Element) -> dict | None:
    meta = record.find("oai:metadata/ax:arXiv", NS)
    if meta is None:  # deleted records have no metadata
        return None
    authors = []
    for a in meta.findall("ax:authors/ax:author", NS):
        name = " ".join(
            x
            for x in (
                _clean(a.findtext("ax:forenames", None, NS)),
                _clean(a.findtext("ax:keyname", None, NS)),
            )
            if x
        )
        if name:
            authors.append(name)
    arxiv_id = _clean(meta.findtext("ax:id", None, NS))
    categories = _clean(meta.findtext("ax:categories", None, NS)).split()
    return {
        "id": arxiv_id,
        "title": _clean(meta.findtext("ax:title", None, NS)),
        "abstract": _clean(meta.findtext("ax:abstract", None, NS)),
        "authors": authors,
        "categories": categories,
        "primary": categories[0] if categories else "",
        "created": _clean(meta.findtext("ax:created", None, NS)),
        "updated": _clean(meta.findtext("ax:updated", None, NS)),
        "doi": _clean(meta.findtext("ax:doi", None, NS)),
        "license": _clean(meta.findtext("ax:license", None, NS)),
        "url": f"https://arxiv.org/abs/{arxiv_id}",
    }


def harvest(
    top_set: str, start: date, end: date, cache: Path, *, new_only: bool = True, progress=None
) -> list[dict]:
    """All records in an OAI set with datestamp in [start, end].

    ``new_only`` keeps papers first submitted (``created``) at most ``NEW_GRACE_DAYS``
    before the window: OAI stamps records when announced (a few days after submission)
    and also re-stamps revisions of old papers, which this drops.
    """
    if top_set not in TOP_LEVEL_SETS:
        raise ValueError(f"Unknown arXiv set {top_set!r}; choose from {sorted(TOP_LEVEL_SETS)}")
    params = {
        "verb": "ListRecords",
        "metadataPrefix": "arXiv",
        "set": top_set,
        "from": start.isoformat(),
        "until": end.isoformat(),
    }
    earliest = (start - timedelta(days=NEW_GRACE_DAYS)).isoformat()
    papers, page = [], 0
    while True:
        text = _get(params, cache)
        root = ET.fromstring(text)
        error = root.find("oai:error", NS)
        if error is not None:
            if error.get("code") == "noRecordsMatch":
                break
            raise RuntimeError(f"OAI error {error.get('code')}: {error.text}")
        for record in root.iterfind("oai:ListRecords/oai:record", NS):
            paper = _parse(record)
            if paper and (not new_only or paper["created"] >= earliest):
                papers.append(paper)
        page += 1
        if progress:
            progress(page, len(papers))
        token = root.findtext("oai:ListRecords/oai:resumptionToken", None, NS)
        if not token:
            break
        params = {"verb": "ListRecords", "resumptionToken": token}
    unique = {p["id"]: p for p in papers}  # a paper can appear on several pages
    return list(unique.values())


def fetch_paper(arxiv_id: str, cache: Path) -> dict:
    """One paper by arXiv id (for seeding likes with older papers)."""
    arxiv_id = re.sub(r"^(https?://arxiv\.org/(abs|pdf)/|arxiv:)", "", arxiv_id.strip(), flags=re.I)
    arxiv_id = re.sub(r"v\d+$", "", arxiv_id.removesuffix(".pdf"))
    try:
        text = _get(
            {
                "verb": "GetRecord",
                "metadataPrefix": "arXiv",
                "identifier": f"oai:arXiv.org:{arxiv_id}",
            },
            cache,
        )
    except urllib.error.HTTPError as exc:
        if exc.code in (400, 403, 404, 406):
            return _abstract_record(arxiv_id, cache)
        raise
    root = ET.fromstring(text)
    record = root.find("oai:GetRecord/oai:record", NS)
    paper = _parse(record) if record is not None else None
    if paper is None:
        raise ValueError(f"arXiv paper {arxiv_id!r} not found")
    return paper


def cached_papers(cache: Path) -> dict[str, dict]:
    """Index previously fetched metadata without making any network requests."""
    papers = {}
    for path in cache.glob("abs-*.html"):
        pid = path.stem.removeprefix("abs-")
        if not re.fullmatch(r"\d{4}\.\d{4,5}", pid):
            continue
        try:
            paper = _abstract_record(pid, cache)
            papers[paper["id"]] = paper
        except (OSError, ValueError):
            continue
    for path in cache.glob("*.xml"):
        try:
            root = ET.fromstring(path.read_text())
            for record in root.iter("{" + NS["oai"] + "}record"):
                paper = _parse(record)
                if paper:
                    papers[paper["id"]] = paper
        except (OSError, ET.ParseError):
            continue
    return papers


def recent_window(days: int, today: date | None = None) -> tuple[date, date]:
    end = today or date.today()
    return end - timedelta(days=days), end
