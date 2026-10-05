"""Download BEIR data and construct a strictly judged-only topic cohort."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import random
import urllib.request
import zipfile

DATA_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/trec-covid.zip"
# Published by BEIR: https://github.com/beir-cellar/beir/wiki/Datasets-available
DATA_MD5 = "ce62140cb23feb9becf6270d0d1fe6d1"


def download(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "trec-covid.zip"
    if not archive.exists():
        temporary = archive.with_suffix(".zip.part")
        request = urllib.request.Request(DATA_URL, headers={"User-Agent": "Lens-research/0.1"})
        print(f"Downloading {DATA_URL}", flush=True)
        try:
            with urllib.request.urlopen(request, timeout=120) as source, temporary.open("wb") as target:
                while block := source.read(1024 * 1024):
                    target.write(block)
            # Check integrity before publishing the cache, without extracting paths.
            with temporary.open("rb") as stream:
                digest = hashlib.file_digest(stream, "md5").hexdigest()
            if digest != DATA_MD5:
                raise ValueError(f"Archive MD5 {digest} does not match published {DATA_MD5}")
            with zipfile.ZipFile(temporary) as zf:
                if zf.testzip() is not None:
                    raise ValueError("Corrupt dataset archive")
            temporary.replace(archive)
        finally:
            temporary.unlink(missing_ok=True)
    return archive


def load_topics(archive: Path, *, count: int, split: str, seed: int, dev_fraction: float = 0.2):
    """Split topics without looking at grades. Negative relevance codes are unjudged.

    BEIR has no official TREC-COVID train/dev split; this is a seeded topic holdout.
    Only qrels keys decide candidate eligibility. Grades never enter retrieval.
    """
    with zipfile.ZipFile(archive) as zf:
        def member(suffix):
            matches = [name for name in zf.namelist() if name.endswith(suffix)]
            if len(matches) != 1:
                raise ValueError(f"Expected one {suffix} file; got {matches}")
            return matches[0]

        with zf.open(member("queries.jsonl")) as source:
            queries = {row["_id"]: row["text"] for line in source if (row := json.loads(line))}
        judgments: dict[str, dict[str, int]] = {}
        with zf.open(member("qrels/test.tsv")) as source:
            for row in csv.DictReader(io.TextIOWrapper(source), delimiter="\t"):
                grade = int(row["score"])
                if grade >= 0:
                    judgments.setdefault(row["query-id"], {})[row["corpus-id"]] = grade
        topic_ids = sorted(set(queries) & set(judgments))
        random.Random(seed).shuffle(topic_ids)
        if not 0 < dev_fraction < 1:
            raise ValueError("--dev-fraction must be between 0 and 1")
        dev_count = max(1, round(len(topic_ids) * dev_fraction))
        cohort = topic_ids[:dev_count] if split == "dev" else topic_ids[dev_count:]
        if not 1 <= count <= len(cohort):
            raise ValueError(f"--topics must be between 1 and {len(cohort)} for {split}")
        selected = cohort[:count]
        wanted = {doc_id for qid in selected for doc_id in judgments[qid]}
        documents = {}
        with zf.open(member("corpus.jsonl")) as source:
            for line in source:
                row = json.loads(line)
                if row["_id"] in wanted:
                    documents[row["_id"]] = row
        missing = wanted - documents.keys()
        if missing:
            raise ValueError(f"Corpus is missing {len(missing)} judged documents")
    return queries, judgments, documents, selected, {
        "split": split,
        "split_seed": seed,
        "dev_fraction": dev_fraction,
        "selected_topics": selected,
        "dev_topic_ids": topic_ids[:dev_count],
        "test_topic_ids": topic_ids[dev_count:],
        "source_url": DATA_URL,
        "archive_sha256": hashlib.file_digest(archive.open("rb"), "sha256").hexdigest(),
        "candidate_eligibility": "explicit judgments >= 0 only; grades withheld from retrieval",
    }
