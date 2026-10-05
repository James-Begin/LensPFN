# Lens showcase

[Watch or download Lens-demo.mp4](Lens-demo.mp4) · **92 seconds · 1920×1080 · 60 fps · H.264/AAC**.

The [repository README](../../README.md#demo) embeds this approved cut through a
[GitHub video attachment](https://github.com/user-attachments/assets/97a7b9f9-82fa-47b8-a80c-9e6cda1d9b5f). The upload is preserved in
[closed media issue #2](https://github.com/James-Begin/LensPFN/issues/2), so it is publicly
available without a login. A direct MP4 download remains in the README, and the same
file is tracked in this folder for playback after cloning. Its SHA-256 is:

```text
eb0342f7b52d958b890e5f01dc1cff0ab403c783543ed8aea73ee677665ca165
```

## What the video represents

A stylized walkthrough of the implemented Lens extension: onboarding, ratings, shortlist
updates, model features, citation previews, top references, and Library. It uses a
browser that fills the frame, typed inputs, wrapping button highlights, smooth reranking,
and a genie transition into the next paper. There are no mouse-click or button sounds.
The original instrumental **Open Horizons** accompanies the film.

Match percentages, timing, and the 88-rating montage are illustrative, rather than a
recorded live inference session. The rating history is consistent within the film.
Metadata extraction represents title/abstract embeddings plus author/category preference
signals; it is not a separate text-generating model. Citation interaction is shown as a
PDF-styled **arXiv HTML** view. The extension does not support citation hovers in a native
browser PDF viewer. Top references appear when scoring completes; they are not tied to
scrolling to the last page in the actual implementation.

## Chapters

| Time | Feature |
| --- | --- |
| 00:00–00:03.4 | Open Lens on arXiv |
| 00:03.4–00:11.0 | Guided setup with typed input |
| 00:11.0–00:30.1 | Accelerating 88-paper reading profile |
| 00:30.1–00:37.7 | Next reads and animated reranking |
| 00:37.7–00:52.9 | Feature extraction, similarity search, and TabPFN |
| 00:52.9–00:58.6 | Read and inspect a citation |
| 00:58.6–01:05.1 | Continue reading and preview TabPFN |
| 01:05.1–01:09.7 | Preview and save TabICL |
| 01:09.7–01:17.1 | Top matches in this paper |
| 01:17.1–01:26.7 | Library and next read |
| 01:26.7–01:32.0 | TabPFN arXiv page and Lens outro |

## Sources and attribution

The reading sequence illustrates pages 1–14 of **TabPFN: One Model to Rule Them All?**
by Qiong Zhang, Yan Shuo Tan, Qinglong Tian, and Pengfei Li, arXiv:2505.20003v2.
The paper has 26 pages including appendices; the film does not claim to read every page.
[Paper and license](https://arxiv.org/abs/2505.20003).

Abstract-page layouts also use public metadata for **Attention Is All You Need**
([1706.03762](https://arxiv.org/abs/1706.03762)) and **TabPFN: A Transformer That Solves
Small Tabular Classification Problems in a Second**
([2207.01848](https://arxiv.org/abs/2207.01848)). Abstract-page prose is abridged/paraphrased
for presentation. The 88 montage papers use public metadata from Lens’s bundled demo
pool/persona; their pages are stylized layouts, not 88 separate PDF captures.

Paper contents and marks retain their rights holders’ terms. No complete paper PDFs,
model weights, tokens, or personal profiles are included in this media directory.
[Repository notices](../../NOTICE.md).

## Validation

- [Export checks](validation/export.json): frame integrity, text widths, every integer
  from 0 to 88 ratings, 59 Interested / 29 Not for me, monotonic typing/scrolling,
  shortlist spacing, extraction order, transitions, audio, and final checksum.
- [Decoded-frame stillness audit](validation/stillness.json): every one of 5,520 encoded
  frames checked at 60 fps. No perceptually static interval exceeds 2.5 seconds; longest
  is 2.35 seconds. Tiny indicators and compression noise do not reset a hold.

These checks accompany visual review; they do not certify every aesthetic property.
The accepted cut contains 2,898 source frames at 30 fps, played 5% faster, and encoded
at 60 fps. This folder carries the approved deliverable and its verification reports;
temporary frame sequences and superseded cuts are omitted.
