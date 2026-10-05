# Optional demo setup

The [92-second showcase](../demo/showcase/Lens-demo.mp4) and GitHub repository are the submission materials.
If you want to try the extension yourself, use the optional steps below. The video’s scores are illustrative; the running
application computes its own estimates.

## Prepare once

Follow [installation](GETTING_STARTED.md#install-and-connect). From `LensPFN/lens/`, stop
any existing companion on port 8765 and run:

```sh
uv run --no-sync python scripts/prepare_demo.py
uv run --no-sync python -m lens.feed.bridge --root .lens-feed-demo --device cpu
```

Use `--device mps` on Apple Silicon or `--device cuda` on an available NVIDIA GPU.

This creates a separate profile with **29 likes, 15 dislikes, and 300 public cs.LG/stat.ML
candidates** from a bundled arXiv week. Its persona ratings are curated examples, not
Scholar Inbox users or the video’s 88-rating history. No arXiv harvest is needed for this
pool. E5 and TabPFN still download on first use; live HTML citations and reference lookup
need network access. No fabricated scores, provider keys, or personal history are shipped.

The helper refuses an existing destination. To make another demo, pass
`--root .lens-feed-demo-2` to both commands. `--limit 0` loads the full bundled 8,211-paper
week and takes longer to embed. The normal `.lens-feed/` remains untouched.

Copy this demo companion’s pairing key from **http://127.0.0.1:8765/**, load the unpacked
extension, and configure your own TabPFN access in guided setup. Without it, the same
walkthrough supports similarity ranking and readable references, with no match percentages.

## Try the features after models are ready

| Step | Try this | Look for |
| --- | --- | --- |
| 1. Start | Open [TabPFN’s abstract](https://arxiv.org/abs/2207.01848) and Lens. | Guided setup or the existing workspace; profile count and connection status. |
| 2. Discover | Open **Next reads**. Expand a candidate’s abstract; rate it Interested or Not for me. | Match estimates with a ready model, an explanation, and a smooth shortlist refresh. |
| 3. Read | Open the [TabPFN survey in HTML](https://arxiv.org/html/2505.20003v2), and hover a linked in-text citation. | The cited paper’s identity and abstract, its own estimate/loading state, and save controls. |
| 4. Follow | Try a reference with only a title or DOI; choose **Open in Lens**. | Automatic closest-version lookup, with bibliography details/manual linking if resolution is unavailable. |
| 5. Save | Mark an unrated citation Interested and keep reading. | Saved state updates without losing the reading position. |
| 6. Review | Let background lookups finish; open **Lens · Top citations** if dismissed. | Up to five highest scored references; unresolved works do not block completion. |
| 7. Return | Open **Library**, then a paper’s arXiv link. | Saved feedback persists and the next read is a normal arXiv paper. |

A paper with many references may need longer for provider lookups, embeddings, and local
inference. Hovered references are prioritized. Citation estimates refresh after five
rating changes; the main shortlist refreshes after each change. Citation estimates exclude
the paper’s own label. Keyboard and reduced-motion interactions are supported.

The [local citation fixture](http://127.0.0.1:8765/html/citation-preview) exercises the
production popup/detector with controlled example references if live arXiv is unavailable.
It is labeled as a fixture and uses this companion’s demo profile for saves.

## Inspect the implementation and evidence

| Question | Read |
| --- | --- |
| Where is TabPFN used? | [`FeedRanker`](../lens/src/lens/feed/rank.py): E5 embeddings + preference signals, `ModelVersion.V3_5_FAST`, local fit/predict. |
| What was measured? | [Frozen plan](../lens/docs/feed-test-preregistration.md), [120-user test results](../lens/docs/results/feedbench.md), and [cold-start analysis](../lens/docs/figures/coldstart_table.md). |
| Why probabilities? | Fast Brier 0.191 vs embedding-logistic 0.208; improved calibration. Ranking superiority is not claimed. |
| How are citations resolved/cached? | [Reference resolver](../lens/src/lens/feed/references.py), [companion](../lens/src/lens/feed/bridge.py), [prefetch queue](../lens/extension/citation-prefetch.js). |
| What stays local? | [Privacy and access](PRIVACY.md). |
| How is it verified? | [Packaging checks](VERIFICATION.md) and [development commands/CI](../CONTRIBUTING.md); tests cover scoring context, auth, references, caching, onboarding, and list motion. |
| What is illustrative? | [Showcase provenance](../demo/showcase/README.md). |

The source is runnable locally; no shared login, hosted Lens server, or browser-store
listing is required. Model licensing and public lookup availability remain external
requirements. This guide packages the project for review; it does not submit it to an event.
