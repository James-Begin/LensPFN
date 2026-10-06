# Lens application

[Main README and demo](../README.md) · [Installation](../docs/GETTING_STARTED.md) · [Development](../CONTRIBUTING.md) · [Evaluation](../docs/research/README.md)

This directory contains the runnable Python package and unpacked Chrome extension.
Run commands here so uv finds the pinned environment.

| Directory | Purpose |
| --- | --- |
| [extension/](extension/README.md) | Browser UI, citation previews, onboarding, and shortlist motion. |
| [src/lens/feed/](src/lens/feed/) | Companion, embeddings, ranking, storage, and reference resolution. |
| [src/lens/feedbench.py](src/lens/feedbench.py) | Reproducible Scholar Inbox evaluation. |
| [scripts/](scripts/) | Demo-profile preparation, benchmark reports, and figure generation. |
| [tests/](tests/) | Python/JavaScript tests and browser interaction fixtures. |

## Optional Streamlit feed

The extension is the main interface. A standalone feed is also available:

```sh
uv sync --locked --extra semantic --extra tabpfn --extra feed
uv run --no-sync streamlit run src/lens/feed/app.py
```

Both interfaces share the default local reading profile. Set `LENS_FEED_HOME` to a
separate path before trying Streamlit's bundled persona: that loader replaces the
selected profile. For a demo that preserves your normal history, use the
[extension demo helper](../docs/DEMO.md).
