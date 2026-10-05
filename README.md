# LensPFN

Lens is a local arXiv reading companion with a Chrome side panel, inline citation previews, and personalized paper match estimates using TabPFN-3.5 Fast.

The editable project is in [`lens/`](lens/). See the [project README](lens/README.md), [extension setup](lens/extension/README.md), and [0.7.0 release notes](lens/docs/releases/0.7.0.md).

```sh
cd lens
uv sync --extra semantic --extra tabpfn --extra feed
uv run --no-sync python -m lens.feed.bridge --device mps
```

Use `--device cpu` on machines without Apple Silicon. In Chrome, enable developer mode, load `lens/extension/` unpacked, and open Lens to complete guided setup. TabPFN access is optional while using similarity ranking.

`lens.zip` is a portable snapshot of the same project. Local credentials, reading profiles, caches and virtual environments are excluded.
