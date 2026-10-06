# Getting started

Lens is a Chrome side panel plus a Python companion running on your computer. The
[main README](../README.md#set-up-on-arxiv) contains the short installation path.

## Install and connect

Use Chrome 116 or later, Git, Python 3.11 or later, and [uv](https://docs.astral.sh/uv/getting-started/installation/).
Commands below assume a terminal opened at the repository root:

```sh
cd lens
uv sync --locked --extra semantic --extra tabpfn --extra feed
uv run --no-sync python -m lens.feed.bridge --device cpu
```

Use `mps` for Apple Silicon or `cuda` for an available NVIDIA GPU. First model downloads
require network access and disk space; CPU embedding/inference can take several minutes.
The extension itself needs no JavaScript build or npm install.

1. Keep the terminal running. Open **http://127.0.0.1:8765/** and copy the pairing key
   from preferences. Use `127.0.0.1`, rather than `localhost`, to match the companion’s host check.
2. At `chrome://extensions`, enable Developer mode and load **`lens/extension/`** unpacked.
   The [extension ZIP](../demo/lens-extension.zip) is an alternative: extract it and load
   the folder containing `manifest.json`.
3. Open an [arXiv abstract page](https://arxiv.org/abs/2207.01848). Open Lens from Chrome’s
   extension menu or pin it to the toolbar. Complete **Connect → Interests → Matches → Read**.
4. Paste the companion pairing key. Add optional interests. Add your own TabPFN token
   when prompted, or skip it to use similarity ranking. Fetch recent papers from the panel.

## TabPFN access and model readiness

The companion runs **TabPFN-3.5 Fast locally**, rather than sending your reading profile to
an inference API. Set up access and accept the model’s terms through
[Prior Labs](https://docs.priorlabs.ai/quickstart). Enter your access token in Lens’s guided
setup; it is verified before replacing existing access and stored outside the checkout
in the local TabPFN authentication cache. Never put a token in a README or source file.

A fresh profile needs **30 ratings, with at least 3 Interested and 3 Not for me** to
unlock displayed match estimates. Until then, the normal shortlist uses similarity and
does not label it as a probability. **Sharpen** can use internal uncertainty estimates
after six ratings, including at least two of each kind; it never displays these early
probabilities. Citation scoring excludes the cited paper’s own rating, so a saved citation
can need one more eligible rating than the main shortlist. The loading indicator means
an estimate is pending; an unavailable score does not prevent saving the paper.

[Prepare an isolated demo](DEMO.md) to try a ready profile without changing your history.

## Read, rate, and follow citations

- Abstract pages add Interested / Not for me actions. The panel’s **Next reads** reranks
  after ratings; **Library** holds rated papers.
- On an arXiv **HTML** paper, hover or keyboard-focus a linked bibliography citation.
  The preview offers metadata, match loading/results, and save actions. Move into the
  popup to keep it open; Arrow Down enters it from its citation, and Escape dismisses it.
- References without arXiv links resolve by public DOI/title metadata. If a reference
  cannot be resolved, inspect its bibliography details, use **Find on arXiv**, or paste
  a known version into **Link an arXiv version**.
- **Top matches in this paper** shows scoring progress and unavailable coverage, then
  suggests up to five references. It also sums match probabilities across distinct,
  resolved, scored references you have not rated. **About N more references you may like**
  is a rounded expectation, not a guaranteed count; the total drops immediately when
  you rate a reference. Close the popup and reopen with **Lens · Top citations**.

PDF viewers are not supported. Some arXiv papers have no HTML version; use their abstract
page and the side panel for ratings and recommendations.

## Digest and Sharpen

Open **Digest** to review papers with genuine match estimates **strictly above 80%**.
Enable **Only notify me above 80% match** for local desktop Chrome alerts. Chrome checks
every 30 minutes while it and the companion are running, using the latest local paper
batch; fetch recent papers to add new candidates. Checks cover all subjects even when
the view is filtered. **Check for new matches** runs a check now. Each new qualifying
paper is marked delivered only after Chrome creates its notification successfully;
empty checks stay silent. Allow Chrome notifications in your browser and OS settings.
The companion web preview can show the digest but cannot create desktop alerts.

Expand **Your 80%+ reality check** to compare first forecasts made before your rating
with your later feedback. It shows how many papers forecast at **80% or higher** you
liked, their average forecast, and a caution for fewer than ten observations. Existing
Library ratings are never backfilled. This describes the papers you chose to rate,
not every arXiv paper or scientific quality.

Open **Sharpen** for up to six unrated papers. It starts with embedding diversity and
reading interests. With TabPFN access and six ratings, including two of each kind, it
balances binary prediction entropy, embedding diversity, and interest relevance within
the model shortlist. Earlier profiles, missing access, or inference failure use diverse
starter papers. Feedback refreshes the queue immediately. This is a practical heuristic,
not formal value of information; faster cold-start learning has not yet been measured.

## Update an existing installation

After updating the source or ZIP, stop and restart the Python companion. Reload Lens
at `chrome://extensions`, then refresh open arXiv tabs. Version 0.8.0 adds Chrome's
`alarms` and `notifications` permissions; desktop alerts remain opt-in.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| Cannot connect | Keep the companion running; visit `127.0.0.1:8765`; copy its pairing key again. Switching `--root` creates a different key. |
| Empty Next reads | Fetch recent papers, or prepare the bundled demo. A new profile has no paper pool. |
| Profile ready; configure TabPFN | Reopen guided setup from preferences and configure your access. Similarity remains usable. |
| Match unavailable | Check the companion terminal, provider access/license acceptance, and available memory. Try `--device cpu` if the accelerator fails. |
| Slow first ranking | Let E5/model downloads and embeddings finish; subsequent runs reuse disk caches. Try the 300-paper demo instead of the full week. |
| Reference lookup busy | Public providers can throttle requests. Retry later or manually link a verified arXiv version. |
| No citation popup | Use arXiv HTML, reload the extension, then refresh the paper tab. Bibliography back-links and native PDFs are excluded. |
| Port already in use | Stop the other companion on 8765 before starting another profile. The extension uses the standard port. |
| New scripts or API routes do not appear | Restart the companion, reload Lens at `chrome://extensions`, and refresh existing arXiv tabs. |
| No digest alert | Enable alerts in Digest, allow Chrome notifications, keep Chrome and the companion running, and fetch a batch. Only new papers strictly above 80% qualify. |

## Optional Streamlit feed

From `lens/`:

```sh
uv run --no-sync streamlit run src/lens/feed/app.py
```

It shares the normal `.lens-feed/` profile with the companion. The sidebar demo loader
replaces that app’s current profile, so use a separate `LENS_FEED_HOME` if exploring it.
The companion demo helper is the safer demo path. [Full extension details](../lens/extension/README.md).
