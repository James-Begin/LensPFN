# Lens for arXiv (local Chrome extension)

[Main README](../../README.md) · [Demo setup](../../docs/DEMO.md) · [Getting started](../../docs/GETTING_STARTED.md)

Lens places two rating buttons on arXiv abstract pages and shows a personal paper shortlist in a Chrome side panel. On arXiv HTML papers, focusing or hovering an in-text bibliography citation opens a paper preview beside it and brings its reference into the Lens side panel. When the reference contains an arXiv ID, the popup shows the verified title, authors, abstract, Interested / Not for me controls, and a TabPFN match estimate when available. It uses the existing local Lens Feed profile, E5 embeddings, and ranking code. It requires a running Python companion; the extension does not contact a hosted Lens service.

## Try the panel first

From the extracted `lens/` project directory:

```bash
uv sync --locked --extra semantic --extra tabpfn --extra feed
uv run --no-sync python -m lens.feed.bridge --device cpu
```

Use `--device mps` on Apple Silicon or `--device cuda` with an available NVIDIA GPU. Open [http://127.0.0.1:8765](http://127.0.0.1:8765) to preview the panel and copy its pairing key from the preferences button. The bridge reuses `.lens-feed/` and `.cache/`, including any batch previously fetched from Streamlit. The bridge only listens on `127.0.0.1`.

To inspect the cited-paper card without installing a browser extension, open [the local citation preview](http://127.0.0.1:8765/?citation=2207.01848). Its sample citation is clearly labelled; the paper metadata and save action use the same local API as the extension.

## Load the extension

1. In Chrome or another Chromium browser with the side panel API, open `chrome://extensions` and turn on **Developer mode**.
2. Choose **Load unpacked** and select the `lens/extension` directory (the directory containing `manifest.json`). If using the current [extension ZIP](../../demo/lens-extension.zip), extract it first and select its `extension` directory.
3. Open an arXiv abstract page such as `https://arxiv.org/abs/2207.01848`. Two Lens rating buttons appear after the title.
4. Open Lens from the browser toolbar or use **Open shortlist** on the paper page. The guided startup flow connects your companion, saves reading interests, and optionally configures TabPFN access. Paste the pairing key from the local companion page when prompted. The key is saved in Chrome extension storage; it is also kept in `.lens-feed/bridge-token` with local file permissions restricted to the current user.

On first opening the extension, Lens presents an animated four-step setup: **Connect → Interests → Matches → Read**. An existing companion connection, reading interests, ratings, and TabPFN access are reused. Reading interests and TabPFN access are optional; skipping keeps existing preferences and allows similarity ranking. A new access token is verified with Prior Labs before it replaces an existing token, stored outside the project in the local TabPFN token cache with file permissions `0600`, and cleared from the form. The provider token is never saved in extension storage or returned by the companion. Chrome extension storage keeps the companion pairing key, setup-completion flag, and a digest opt-in mirror; session storage also holds the active paper/reference context. Complete setup once to enter the shortlist directly on subsequent openings. **Open guided setup** in preferences lets you revisit it. Reduced-motion preferences remove the entrance and step movement.

Preview the setup at [http://127.0.0.1:8765/?setup=1](http://127.0.0.1:8765/?setup=1). The companion’s normal page still opens directly to the workspace so its pairing key can be copied immediately from preferences. A new profile needs 30 ratings, including at least 3 Interested and 3 Not for me, before match estimates are available; TabPFN model-license acceptance remains in your Prior Labs account.

To follow a citation, open an arXiv **HTML** paper and hover a linked in-text bibliography citation. The popup stays open while you move into it. Rate the paper there, expand its abstract, or choose **Open in Lens** to see it in the side panel. With a keyboard, Tab to a citation, press Arrow Down to enter its popup, and Escape to dismiss. The original reference link still works. References without an arXiv ID show their bibliography text, with title, authors, publication, year, and a DOI or source link when the markup provides them. Their details also appear in the side panel. Lens first checks locally cached papers, then looks up their DOI or title through Semantic Scholar. When that lookup is throttled or finds no arXiv identity, Lens searches arXiv DOI deposits through DataCite’s public API. These deposits include authors and abstracts, so the popup can display and score the paper without another metadata download. Provider cooldowns are respected, and temporary failures can be retried by hovering again. Lens automatically selects the closest arXiv version and scores it without confirmation. Title agreement determines the best match, with authors and year breaking ties; canonical arXiv metadata or arXiv’s DOI deposit is used for scoring. If the lookup is unavailable or finds no version, use **Find on arXiv**, then expand **Link an arXiv version** and paste an arXiv URL or ID. Once linked, match scores and library saving work normally. A manual link is remembered while this paper tab remains loaded. If the work has no identifiable arXiv version, its reference remains readable but cannot be scored yet. Bibliography label links and back-links into the paper being read are excluded from cited-paper identification. The detector accepts bibliography entries with nonstandard anchor IDs, full same-page links, HTML/PDF/export/ar5iv links, and arXiv DOI identifiers. PDFs are not supported.

Once citation scoring finishes, **Top matches in this paper** opens beside the reading page with up to five highest matches, their authors, and Interested / Open in Lens actions. Repeated references are counted once; papers marked Not for me and the paper being read are excluded from suggestions. References that cannot be identified or scored are reported without blocking completion. Close the popup with its close button or Escape, and reopen it with **Lens · Top citations**. The popup opens automatically once per loaded paper and does not steal keyboard focus. The expected remaining count updates immediately after a rating; the underlying scores still refresh after five rating changes, and the popup remains closed if you dismissed it. During scoring it shows checked/total progress and unavailable coverage. The remaining expectation sums probabilities over distinct resolved, scored, unrated references; both positive and negative ratings remove a paper from that total. **About N more references you may like** rounds this sum, rather than promising N relevant papers. Unresolved and unscored references do not contribute.

Citation match estimates use your other ratings: the cited paper's own rating is excluded, and the remaining profile must meet the 30-rating / 3-of-each threshold. Opening an HTML paper automatically queues metadata and match estimates for each distinct identified citation when your profile is ready and TabPFN is configured. One background lookup runs at a time, and a hovered citation moves ahead of queued work. Completed estimates are reused on hover. Citation scores share a fixed rating snapshot and refresh after five real rating changes (positive, negative, flips, or removals); rating buttons and the main shortlist still update immediately. Changing interests, crossing the model readiness threshold, editing the profile externally, or restarting the companion resets citation estimates immediately. The title and save controls are usable while the estimate loads. A “Checking match” label and animated dots occupy the match position until a score or warning arrives; reduced-motion settings show static dots.

After feedback, the old shortlist stays visible while Lens ranks the next batch. Existing papers move to their new positions and new papers arrive with a short, capped stagger. Reduced-motion preferences remove spatial movement. Expanded abstracts and keyboard focus are preserved where applicable.

Start the companion whenever you want the extension to work. On a new profile, the shortlist shows recently announced papers until you rate a paper or add interests. After 30 ratings, including at least 3 positive and 3 negative ratings, Lens can show TabPFN match estimates if authorized TabPFN model access has been configured. Without that access it continues with similarity ranking and says so in the panel.

Use **Fetch recent arXiv papers** in the panel to harvest a new three-day computer science batch. The companion follows arXiv's OAI-PMH request spacing and caches metadata. If a single-paper OAI lookup is unavailable, rating that paper uses public abstract-page metadata instead. Fetching can take several seconds; first-time embedding of a large batch also takes time. Other archives can still be fetched from the Streamlit application.

Reference resolution sends only public bibliography DOI/title/reference text to Semantic Scholar and DataCite; it does not send your ratings, interests, or profile. Lookup responses are cached for a day; transient failures remain retryable. The existing background prefetch queue handles these lookups too.

The extension requests access only to arXiv abstract and HTML pages and the loopback companion. It does not access PDFs, browsing history, or other websites. The pairing key keeps ordinary web pages from changing your local profile. Treat the key as a local credential; don't share it.

## Quiet digest and a sharper profile

**Digest** lists unrated papers with genuine match estimates **strictly above 80%** in the latest local batch. The subject control filters this view; background alert checks cover all subjects. Enable **Only notify me above 80% match** to let desktop Chrome check every 30 minutes while Chrome and the companion are running. Use **Check for new matches** to check immediately, and fetch recent arXiv papers to add new candidates. No qualifying new papers means no notification. Similarity scores never trigger alerts.

Alerts are opt-in and require Chrome/OS notification permission. A successful Chrome notification creation acknowledges each included paper in the local profile, so it alerts once. Permission denial or notification failure leaves the papers pending. Clicking the notification opens Digest. The companion-only web preview cannot send native desktop alerts.

**Your 80%+ reality check** compares first genuine forecasts saved before feedback with later ratings for papers forecast at 80% or higher. It reports liked X of Y, the observed percentage, the mean forecast, and a small-sample caution below ten observations. It does not backfill existing Library history and describes only the papers you chose to rate, rather than all arXiv papers.

**Sharpen** chooses up to six unrated papers. At six ratings with at least two Interested and two Not for me, configured TabPFN access allows internal binary prediction entropy to guide selection from the 300-paper model shortlist, weighted by embedding diversity and reading interests. Before that point, without access, or on inference failure, it uses diverse starter papers. Feedback invalidates the queue immediately. Early probabilities are not displayed; normal shortlist/citation match readiness remains 30 ratings with at least three of each kind, excluding a citation's own rating. This is an uncertainty heuristic, not formal value of information, and it has not yet been shown empirically to accelerate cold-start learning.

Digest preferences, prospective forecasts, and offered/delivered IDs are stored privately in `insights.json` under the selected profile root, with mode `0600`. Chrome adds `alarms` and `notifications` permissions. Provider tokens continue to use the existing external TabPFN credential cache. [Privacy details](../../docs/PRIVACY.md).

## Updating to 0.8.0

Restart the Python companion after updating the source. Reload Lens at `chrome://extensions`, then refresh open arXiv tabs. Review Chrome's added permissions if prompted; the digest remains disabled until you opt in. [Release notes and validation limits](../../docs/research/releases/0.8.0.md).

## Development

The extension is plain Manifest V3 JavaScript and CSS with no JavaScript build step. `content.js` adds the abstract-page controls; `citation-prefetch.js` schedules and caches background lookups; `reference-parser.js` reads bibliography markup and identifiers; `citations.js` detects linked HTML citations; `citation-popup.js` renders their isolated popup; `list-motion.js` animates reranking; `digest.js` coalesces checks and acknowledges successful alerts; `background.js` limits and relays requests to the local companion and runs its opt-in Chrome alarm; `panel.html`, `panel.js`, and `panel.css` implement the side panel. The Python companion is `src/lens/feed/bridge.py`.

```bash
uv run --no-sync python -m unittest discover -s tests -v
node --check extension/background.js
node --check extension/content.js
node --check extension/citation-prefetch.js
node --check extension/reference-parser.js
node --check extension/citations.js
node --check extension/citation-popup.js
node --check extension/list-motion.js
node --check extension/panel.js
node --test tests/test_*.cjs
```

The panel can be previewed and exercised at `http://127.0.0.1:8765/` without installing the extension. A handwritten citation fixture is available at `http://127.0.0.1:8765/html/citation-preview` in the full source checkout; it runs the production popup and detector with a local transport. Its ratings use the companion's profile. Popup hover, keyboard interaction, saving, unresolved references, and a 390px viewport were checked in Chrome with an isolated test profile. The 0.8.0 pass used the in-app browser with isolated profiles at 1280px and 390px; native Chrome notification banners and live arXiv integration were not newly verified. Service-worker tests cover denied permissions, successful creation before acknowledgement, overlapping checks, offline alarms, and authentication failures. TabPFN-3.5-Fast shortlist and individual citation probabilities were verified on Apple Silicon (MPS). Credentials are stored outside this project in TabPFN's local authentication cache.
