# Notices and licensing

Lens is an independent project, built for the TabPFN-3.5 hackathon. It is not endorsed
by arXiv or Prior Labs. This repository currently has no standalone source-code license;
third-party licenses are not a grant of a license to the Lens code.

## Models and dependencies

- **TabPFN-3.5 / Fast:** model weights are obtained separately through Prior Labs and
  retain their model-license terms. The project’s original research notes identify
  TABPFN-3.5 License v1.0 for non-commercial/evaluation use; check the terms presented
  during [model access setup](https://docs.priorlabs.ai/quickstart) for your use.
  No model weights or provider credentials are redistributed here.
- **E5-small-v2:** [`intfloat/e5-small-v2`](https://huggingface.co/intfloat/e5-small-v2)
  is downloaded separately and retains its upstream terms.
- Python dependencies are declared in [`lens/pyproject.toml`](lens/pyproject.toml) and
  pinned in [`lens/uv.lock`](lens/uv.lock). Each dependency retains its own license.

## Metadata and evaluation

- **arXiv metadata:** bundled public metadata is provided under CC0. API access is subject
  to [arXiv’s API terms](https://info.arxiv.org/help/api/tou.html). The running extension
  links to paper pages; it does not serve PDFs.
- **Scholar Inbox ratings:** CC BY-NC-ND 4.0; used only for evaluation, not redistributed.
  [Dataset source](https://github.com/avg-dev/scholar_inbox_datasets) ·
  [Scholar Inbox paper](https://arxiv.org/abs/2504.08385).
- **Demo persona:** curated example labels on public arXiv metadata. It is not a real
  benchmark user or the repository owner’s profile.

## Showcase

The demo film includes attributed paper-page illustrations and public metadata. Paper
content and arXiv/TabPFN names remain the property of their respective rights holders;
no blanket license over those materials is asserted. The video’s original instrumental
music is synthesized for this showcase. Match values and the accelerated reading history
are illustrative. [Sources, chapters, and validation](docs/DEMO.md#showcase-provenance).
