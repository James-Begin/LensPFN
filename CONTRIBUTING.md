# Development

The extension uses plain Manifest V3 JavaScript and CSS; there is no Node build step.
The companion, ranking pipeline, and research tools are in `lens/src/lens/`.

From the repository root:

```sh
cd lens
uv sync --locked --extra semantic --extra tabpfn --extra feed
uv run --no-sync python -m unittest discover -s tests -v
node --test tests/test_*.cjs
```

The unit tests also run with `uv sync --locked` alone: model calls and public API calls
are mocked. They do not require a provider token, GPU, model download, or your reading profile.
Node 22 or later is recommended for extension tests. CI runs both suites.

For a live walkthrough, follow the [demo guide](docs/DEMO.md). Use a separate
`--root` and `--cache` when testing changes; the normal profile lives in `lens/.lens-feed/`.
Reload the unpacked extension in `chrome://extensions`, then refresh open arXiv tabs after
changing content scripts. [Extension architecture and interaction checks](lens/extension/README.md#development).

To update the downloadable extension after editing its files, run from the repository root:

```sh
python3 scripts/package_extension.py
python3 scripts/check_submission.py
```

This deterministic ZIP contains only extension source and icons, with no profile, pairing
key, token, cache, environment, or model weights. The original project ZIP is retained
under [archive/](archive/README.md); the editable checkout is the current source of truth.
The submission check verifies local documentation links, manifest assets, package/source
agreement, common credential patterns, and the approved movie checksum.

Keep documentation claims tied to [reported results](lens/docs/results/feedbench.md),
and distinguish measured inference from illustrative media. Do not commit personal
profiles, credentials, model weights, or Scholar Inbox ratings/predictions. Describe the
trigger, resulting behavior, and validation when proposing a change.
