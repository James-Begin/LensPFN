# Product
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
Researchers reading papers on arXiv. Initial local user: the repository owner.

## Product Purpose
Lens learns personal paper interests from explicit ratings and produces a shortlist. The user selected: rate papers on arXiv and open a ranked shortlist in a side panel.

## Operating Context
Existing Python Lens Feed application and local profile. New browser-extension surface complements arXiv abstract pages; arXiv's reading surface remains intact.
On HTML papers, linked in-text citations open an inline preview and can be brought into the side panel for a canonical arXiv lookup, explicit ratings, and personal match estimates. Shortlist updates preserve reading continuity with bounded arrival and reordering motion.

## Capabilities and Constraints
Reuse E5 embeddings, Rocchio cold start, and optional TabPFN ranking. Local Python process owns model execution and profile persistence. TabPFN-3.5-Fast access and local MPS inference were verified on October 4, 2026. Credentials stay outside the project. Never label similarity scores as probabilities. No background notification service currently exists.

## Evidence on Hand
README and docs/results contain reported benchmark results, not independently reproduced here. Local arXiv metadata and 603 cached E5 vectors are available. Do not invent ratings, match percentages, or model-access claims.

## Open Decisions
Browser target assumption for this first implementation: Chrome/Chromium Manifest V3. Distribution is unpacked/local; no store publication requested. A hosted backend or Safari/Firefox port is outside the initial scope.

Citation previews also read structured bibliography entries without arXiv IDs. They provide source details and DOI links when present; match estimates and paper ratings still require a verified arXiv identity. Pending citation scores have an explicit loading indicator.

Citation prefetch (0.4.0): when an HTML paper opens, automatically queue identified citations for local metadata and match estimates. Deduplicate references, limit background work to one lookup, and prioritize hovered citations. Reuse estimates for five rating changes while saved button state and feed shortlist remain current. Immediately reset citation scores for interest edits and model readiness transitions.

Reference resolution (0.5.0): references without arXiv links may still have an arXiv version. Resolve DOI mappings via Semantic Scholar and validate canonical title metadata before scoring. Title candidates automatically select the closest supported arXiv version, following the user’s preference. Provide a search link and manual arXiv URL/ID linking for unresolved references. Works without an identifiable arXiv version remain unscored. Public bibliography lookup does not transmit the preference profile.
