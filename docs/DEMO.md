# Optional demo setup

The [updated showcase](../README.md#demo) and GitHub repository are the submission materials.
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
candidates** selected from public arXiv metadata harvested September 25–October 2, 2026. Its persona ratings are curated examples, not
Scholar Inbox users or the video’s 88-rating history. No arXiv harvest is needed for this
pool. E5 and TabPFN still download on first use; live HTML citations and reference lookup
need network access. No fabricated scores, provider keys, or personal history are shipped.

The helper refuses an existing destination. To make another demo, pass
`--root .lens-feed-demo-2` to both commands. `--limit 1` through `--limit 300` selects a smaller subset of the fixed demo pool. The normal `.lens-feed/` remains untouched.

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
| What was measured? | [Frozen plan](https://github.com/James-Begin/LensPFN/blob/a4e3f6fb3073f93be3a30736630888451fb3cbc2/docs/research/feed-test-preregistration.md), [120-user test results](research/results/feedbench.md), and [cold-start analysis](research/figures/coldstart_table.md). |
| Why probabilities? | Fast Brier 0.191 vs embedding-logistic 0.208; improved calibration. Ranking superiority is not claimed. |
| How are citations resolved/cached? | [Reference resolver](../lens/src/lens/feed/references.py), [companion](../lens/src/lens/feed/bridge.py), [prefetch queue](../lens/extension/citation-prefetch.js). |
| What stays local? | [Privacy and access](PRIVACY.md). |
| How is it verified? | [Packaging checks](VERIFICATION.md) and [development commands/CI](../CONTRIBUTING.md); tests cover scoring context, auth, references, caching, onboarding, and list motion. |
| What is illustrative? | [Showcase provenance](#showcase-provenance). |

The source is runnable locally; no shared login, hosted Lens server, or browser-store
listing is required. Model licensing and public lookup availability remain external
requirements. This guide packages the project for review; it does not submit it to an event.

## Showcase provenance

The README embeds the 113.12-second revised film as a GitHub video attachment, preserved in [closed media issue #3](https://github.com/James-Begin/LensPFN/issues/3). The video is hosted outside the Git source tree.

### What the video represents

A stylized walkthrough of the implemented Lens extension: onboarding, Sharpen, 88 ratings,
shortlist updates, feature extraction, citation previews, the remaining-reference estimate,
top references, Digest, and the prospective reality check. A browser fills the frame;
inputs appear typed and button highlights wrap around controls. The reality-check action
launches the TabPFN paper with a genie transition. There are no mouse-click or button
sounds. The original instrumental **Open Horizons** accompanies the film.

Scores, feedback, notification banners, and timing are illustrative, not a recorded live
inference session. Sharpen starts with diverse suggestions at zero ratings; uncertainty
guidance becomes available later in the actual product. Its faster-learning benefit has
not been established. The normal match-percentage threshold remains 30 ratings,
including three of each kind.

The reference fixture has seven scored references and two unresolved. Four distinct,
unrated forecasts sum to 2.99 expected likes (about 3). Saving TabPFN removes its 0.93
probability, leaving 2.06 (about 2). The estimate covers scored references and is not a
guaranteed count. The staged reality-check ledger incorporates that same reaction:
14/16 becomes 15/17; no extra rating or backfilled forecast is created. Digest checks the
local scored pool; the notification illustration does not imply automatic arXiv fetching.

Metadata extraction represents title/abstract embeddings plus author/category preference
signals; it is not a text-generating model. Citation interaction is shown as a PDF-styled
**arXiv HTML** view; native PDF citation hovers are unsupported. The new reference scenes
stay on page 12 of 26 before the reader reaches the end. In the actual extension, top
references appear when scoring completes, independently of the scroll position.

### Chapters

Times are approximate around overlapping transitions.

| Time | Feature |
| --- | --- |
| 00:00–00:03.4 | Open Lens on arXiv |
| 00:03.4–00:10.6 | Guided setup with typed input |
| 00:10.6–00:22.1 | Sharpen your profile and inspect a starter paper |
| 00:22.1–00:40.5 | Accelerating 88-paper reading profile |
| 00:40.5–00:48.1 | Next reads and animated reranking |
| 00:48.1–01:03.3 | Feature extraction, similarity search, and TabPFN |
| 01:03.3–01:14.6 | Read while Lens checks; reach the TabPFN citation |
| 01:14.6–01:22.5 | How much is left worth exploring? |
| 01:22.5–01:30.1 | Top matches and a TabPFN reaction |
| 01:30.1–01:39.9 | Quiet digest and an illustrative local alert |
| 01:39.9–01:48.1 | Prospective reality check and Read TabPFN |
| 01:48.1–01:53.1 | TabPFN arXiv page and Lens outro |

### Sources and attribution

The reading sequence illustrates pages from **TabPFN: One Model to Rule Them All?**
by Qiong Zhang, Yan Shuo Tan, Qinglong Tian, and Pengfei Li, arXiv:2505.20003v2.
The paper has 26 pages including appendices; the film does not claim to read every page.
[Paper and license](https://arxiv.org/abs/2505.20003).

Abstract-page layouts also use public metadata for **Attention Is All You Need**
([1706.03762](https://arxiv.org/abs/1706.03762)) and **TabPFN: A Transformer That Solves
Small Tabular Classification Problems in a Second**
([2207.01848](https://arxiv.org/abs/2207.01848)). The digest uses metadata for
**Can transformers learn full Bayesian inference in context?**
([2501.16825](https://arxiv.org/abs/2501.16825)). Abstract-page prose is abridged/paraphrased
for presentation. The 88 montage papers use public metadata from Lens’s bundled demo
pool/persona; their pages are stylized layouts, not 88 separate PDF captures.

Paper contents and marks retain their rights holders’ terms. No complete paper PDFs,
model weights, tokens, or personal profiles are included in the repository.
[Repository notices](../NOTICE.md).


### Export checks

The final MP4 is H.264/AAC at 1920×1080 and 60 fps, with 6,787 decoded frames. TypeScript and ESLint pass; 57 sampled action/boundary frames have no text-width or browser-bound issues. A separate montage handoff check covers 21 consecutive encoded frames and reports no blank frames. A full decoded-frame audit checks meaningful stillness, ignoring compression noise and tiny indicators: the longest unchanged stretch is 2.42 seconds, below the 2.5-second limit. Detailed local export reports are retained outside the repository.

Export SHA-256: `49567015a8505230ef15296dc4e1aaa34555fa2d689dfde3966057586c0a92b8`.
