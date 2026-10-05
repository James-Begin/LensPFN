"""Label-free CORD-19 document metadata features (publication date, source, venue, ...).

Source: CORD-19 release 2020-07-16 metadata.csv (the snapshot TREC-COVID round 5 used),
joined on cord_uid == BEIR document id. Nothing here is derived from relevance
judgments; features are computed per document, independently of any topic.
"""
from __future__ import annotations

import csv
from datetime import date
import json
import math
from pathlib import Path
import re
import shutil
import sys
import urllib.request

import numpy as np

METADATA_URL = "https://ai2-semanticscholar-cord-19.s3-us-west-2.amazonaws.com/2020-07-16/metadata.csv"
METADATA_BYTES = 269219095  # Content-Length reported by the bucket
SOURCES = ["PMC", "Medline", "WHO", "Elsevier", "MedRxiv", "BioRxiv", "ArXiv"]
LICENSES = ["cc-by", "els-covid", "no-cc", "cc-by-nc", "medrxiv", "biorxiv", "arxiv"]
COVID = re.compile(r"covid|sars-cov-2|2019-ncov|novel coronavirus|wuhan", re.I)
COLUMNS = (["year", "months_since_2020", "is_2020", "date_known"]
           + [f"source_{s.lower()}" for s in SOURCES]
           + [f"license_{x}" for x in LICENSES]
           + ["log_journal_count", "has_journal", "log_authors", "has_full_text",
              "has_doi", "title_len", "covid_in_title", "covid_in_abstract"])


def download(cache: Path) -> Path:
    path = cache / "cord19-2020-07-16-metadata.csv"
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".part")
        print(f"Downloading {METADATA_URL}", flush=True)
        with urllib.request.urlopen(METADATA_URL, timeout=120) as src, part.open("wb") as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
        if part.stat().st_size != METADATA_BYTES:
            raise ValueError(f"metadata.csv size {part.stat().st_size} != expected {METADATA_BYTES}")
        part.replace(path)
    return path


def _date_features(text: str):
    m = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", text or "")
    if not m:
        return [math.nan, math.nan, math.nan, 0.0]
    year, month, day = int(m.group(1)), int(m.group(2) or 7), int(m.group(3) or 1)
    try:
        months = (date(year, month, day) - date(2020, 1, 1)).days / 30.44
    except ValueError:
        months = (year - 2020) * 12.0
    return [float(year), months, float(year == 2020), 1.0]


def document_table(metadata_csv: Path, ids: set[str]):
    csv.field_size_limit(sys.maxsize)
    rows, journals = {}, {}
    with metadata_csv.open(newline="", encoding="utf-8") as stream:
        for r in csv.DictReader(stream):
            journal = (r.get("journal") or "").strip().lower()
            if journal:
                journals[journal] = journals.get(journal, 0) + 1
            uid = r["cord_uid"]
            if uid in ids and uid not in rows:  # metadata.csv has duplicate cord_uids; keep first
                rows[uid] = r
    table = {}
    for uid, r in rows.items():
        sources = (r.get("source_x") or "")
        license_ = (r.get("license") or "").strip().lower()
        journal = (r.get("journal") or "").strip().lower()
        authors = [a for a in (r.get("authors") or "").split(";") if a.strip()]
        full = bool((r.get("pdf_json_files") or "").strip() or (r.get("pmc_json_files") or "").strip())
        title, abstract = r.get("title") or "", r.get("abstract") or ""
        table[uid] = (_date_features(r.get("publish_time", ""))
                      + [float(s.lower() in sources.lower()) for s in SOURCES]
                      + [float(license_ == x) for x in LICENSES]
                      + [math.log1p(journals.get(journal, 0)) if journal else 0.0, float(bool(journal)),
                         math.log1p(len(authors)), float(full), float(bool((r.get("doi") or "").strip())),
                         math.log1p(len(title.split())), float(bool(COVID.search(title))),
                         float(bool(COVID.search(abstract)))])
    return table


def add_metadata(*, source: Path, output: Path, cache: Path):
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"{output} is not empty; use a new artifact directory")
    manifest = json.loads((source / "manifest.json").read_text())
    qids = manifest["selected_topics"]
    ids = set()
    for q in qids:
        with np.load(source / f"topic-{q}.npz", allow_pickle=False) as src:
            ids.update(src["doc_ids"].tolist())
    table = document_table(download(cache), ids)
    missing = ids - table.keys()
    print(f"Metadata for {len(table)}/{len(ids)} documents ({len(missing)} missing -> NaN)", flush=True)
    output.mkdir(parents=True)
    blank = [math.nan] * len(COLUMNS)
    for q in qids:
        with np.load(source / f"topic-{q}.npz", allow_pickle=False) as src:
            arrays = {k: src[k] for k in src.files}
        arrays["docmeta"] = np.array([table.get(d, blank) for d in arrays["doc_ids"]], dtype=np.float32)
        np.savez_compressed(output / f"topic-{q}.npz", **arrays)
        shutil.copy(source / f"topic-{q}.json", output / f"topic-{q}.json")
    manifest["docmeta_columns"] = COLUMNS
    manifest["docmeta_source"] = METADATA_URL
    manifest["derived_from_metadata"] = str(source)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {output}", flush=True)
