# Data, access, and privacy

Lens has no hosted account or telemetry service. A local companion listens on
`127.0.0.1:8765` and owns persistence and inference.

| Data or operation | Where it goes |
| --- | --- |
| Interested / Not for me ratings, interests, Library | The selected local profile root; normally `lens/.lens-feed/`. |
| E5 embeddings, arXiv metadata, reference responses | Local disk under the companion’s cache directory; normally `lens/.cache/`. |
| TabPFN predictions | Local model execution using your profile as context. |
| Prospective forecasts, digest opt-in, offered/delivered paper IDs | `insights.json` in the selected local profile root, saved with mode `0600`; ignored by Git and excluded from the ZIP. |
| Digest notifications | Local Chrome/OS notifications containing public paper titles and the number of new high matches; no hosted delivery service. |
| Provider access setup | Token verification with Prior Labs; accepted token saved outside the repository, normally `~/.cache/tabpfn/auth_token`. |
| First-use model downloads | Model/provider download endpoints. Model weights are not bundled in this repo. |
| Paper harvesting | Public arXiv metadata APIs, rate-limited and cached. |
| Reference resolution | Public bibliography DOI, title, authors/year, or reference text sent to Semantic Scholar and DataCite. Your ratings and interests are not included. |

The pairing key authenticates extension-to-companion requests. It is kept locally in
`bridge-token` and in Chrome extension storage; it is separate from provider access.
The provider token is verified before replacement, written atomically with mode `0600`,
and never returned to the extension or stored in extension storage. Authorization headers,
interests, and pairing keys are excluded from HTTP logs.

Chrome extension storage also keeps the digest opt-in mirror used to restore its alarm;
provider credential storage is unchanged. Forecast history starts with genuine estimates
before feedback and does not reconstruct predictions for existing Library ratings.

The extension requests `storage`, `sidePanel`, `alarms`, and `notifications`, loopback
access, and content-script access to arXiv abstract/HTML pages. The opt-in digest alarm
checks the local companion every 30 minutes. Delivered IDs are recorded after Chrome
creates the notification successfully, so denied or failed notifications stay pending.
It does not read browsing history or native PDFs.
[Manifest](../lens/extension/manifest.json) · [Companion auth](../lens/src/lens/feed/bridge.py) ·
[Provider access storage](../lens/src/lens/feed/access.py).

Profiles and caches are ignored by Git and excluded from the extension ZIP. The judge
demo uses bundled public metadata and a curated persona in a separate profile folder.
It contains no personal reading history, evaluation users, or shared credentials.
