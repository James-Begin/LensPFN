---
name: Lens for arXiv
description: A quiet reading margin for rating arXiv papers and reviewing a personal shortlist.
colors:
  paper: "#ffffff"
  ink: "#242329"
  muted: "#655f68"
  line: "#dedbe0"
  soft: "#f5f3f5"
  accent: "#8c253b"
  accent-soft: "#f9eef1"
  success: "#306647"
typography:
  display:
    fontFamily: "Georgia, Times New Roman, serif"
    fontSize: "30px"
    fontWeight: 400
    lineHeight: 1.15
  paper-title:
    fontFamily: "Georgia, Times New Roman, serif"
    fontSize: "20px"
    fontWeight: 400
    lineHeight: 1.38
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  control: "6px"
spacing:
  compact: "8px"
  regular: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  rating-selected:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent}"
    rounded: "{rounded.control}"
---

# Design System: Lens for arXiv

## Overview

Lens is a narrow reading margin attached to arXiv abstract pages. It keeps the host site's white paper surface and burgundy accent, while giving the personal shortlist enough space for scannable titles, authors, subjects, and explicit feedback. The panel is calm and editorial; model status is explained in plain language.

## Colors

White is the reading surface, near-black carries paper titles, and a muted gray handles metadata. Burgundy marks chosen actions, active navigation, and focus. Green is reserved for a connected companion and actual match estimates. Thin neutral rules separate papers; pale burgundy backs the learning guide and selected ratings.

## Typography

Georgia gives the shortlist heading and paper titles the same reading character as arXiv. System sans handles controls, metadata, and explanatory copy. Paper titles are 20px with a 1.38 line height; metadata and controls are at least 12px. Avoid all-caps decoration and truncated paper titles.

## Layout

The extension side panel is a single column, up to 480px wide, with 24px gutters (17px below 360px). The first viewport presents connection, navigation, shortlist context, and the beginning of the paper list. Each paper has a metadata line, a linked title, authors, optional reason, abstract disclosure, and two rating actions. At desktop preview widths the column stays centered; the browser side panel uses the same narrow layout.

## Elevation & Depth

The reading surface is flat and uses rules for separation. The standalone preview has a faint shadow only to distinguish the simulated side panel from its background. The transient confirmation message floats above content; paper rows do not use card shadows.

## Shapes

Controls and the learning guide have a 6px radius. Paper rows remain rectangular. The tiny circular connection indicator is the only prominent round shape.

## Components

**Ratings:** Interested and Not for me are paired, reversible buttons. The chosen action uses a pale burgundy fill and burgundy border. The text label stays visible next to its icon; pressed state is exposed to assistive technology.

**Paper rows:** Titles are links to canonical arXiv abstract pages. Abstracts open inline; reranking preserves the open state for papers still visible. If rating removes a paper from the shortlist, focus moves to the next paper link.

**Status and onboarding:** The companion status remains visible near the masthead. Before model estimates are available, the learning guide shows progress toward 30 ratings, including at least 3 Interested and 3 Not for me ratings. Recent and similarity ranked lists do not display invented match percentages.

**Cited paper:** A slim burgundy guide rule sets a focused citation apart from the page currently being read. The sidebar names the highlighted reference, shows canonical arXiv metadata, and offers a save action and an actual match estimate when available. Beside the inline citation, an isolated white popup presents the paper title, authors, abstract, rating controls, match estimate, and Open in Lens. Its transient shadow distinguishes the preview from the document; the source reference remains a working link. Hover is delayed 180ms to avoid accidental activation, and a 280ms dismissal grace bridges the gap into the popup. Arrow Down enters it from a focused citation; Escape returns focus.

**Reranking motion:** The current list remains visible during scoring, accompanied by an Updating your shortlist status. Familiar rows move from their previous positions over 300ms; new rows arrive with a 280ms horizontal reveal, staggered by 28ms and capped at 168ms total delay. Content is visible by default, animations can be interrupted, and reduced-motion preferences update rows immediately. Popup entry uses a single 160ms transition and skips movement for reduced motion.

## Do's and Don'ts

- Keep arXiv content intact and place the extension controls beside the user's reading flow.
- Use clear explanations of ranking state and errors.
- Preserve visible focus, keyboard access, and reduced-motion behavior.
- Do not turn the panel into a dashboard or imply that similarity scores are probabilities.

Citation refinement (0.3.1): show parsed bibliography details in unresolved previews and retain the complete reference when title boundaries are uncertain. During scoring, the match position reads “Checking match” with three fading dots; it settles to the percentage or clears on a warning/error. Reduced motion uses static dots. Source links are limited to HTTP(S).

Citation prefetch (0.4.0): warm estimates before interaction; a warm hover shows its existing score without waiting for another model call. Preserve the existing checking indicator for unfinished lookups. Citation score snapshots last five rating changes; Interested / Not for me state changes immediately. Background work is serial, with hovered citations moved ahead of pending jobs.

Unresolved-reference recovery (0.5.0): retain full bibliography text while looking up a DOI/title. Show titled candidates with authors for confirmation. The popup offers Find on arXiv and an expandable Link an arXiv version field; metadata and scores replace the fallback only after identification. Keep these recovery controls available on lookup failure, preserve keyboard access, and limit the popup to its existing viewport bounds.
