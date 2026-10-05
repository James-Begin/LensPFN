# Hackathon brief and initial brainstorm

## Brief (as provided)
TabPFN-3.5 Hackathon (Prior Labs). Open-ended; creativity counts as much as performance;
a Prior Labs panel picks top 3 + honorable mentions. Tracks: build an agent; build an
extension/MCP/app; take on a hard problem; formalize a new problem as tabular; showcase a
harness (e.g. TabPFN-Rel); your own idea.

Verified from public posts (LinkedIn, Sept 2026): runs through **October 6**; prizes
DGX Spark / Jetson AGX Orin / RTX 4090; submit a **runnable repository**, optional demo
video. No detailed scoring rubric was found.

## TabPFN-3.5 facts used for planning
Source: technical report https://arxiv.org/html/2609.17895v1
- 220M params (Fast: 84M); recommended up to 1M rows × 6,000 features; single
  classification+regression checkpoint; predictive distributions in one forward pass.
- #1 on TabArena, BeyondArena, STRABLE, MulTaBench, ScoringBench (CRPS), TALENT; TabPFN-Rel
  #1 on RelArena-α. Through TabPFN-TS it places 6th/29 on fev-bench (not best forecaster).
- Cached inference = fixed context; adding rows means refitting.
- Plus/Thinking are API-only; open weights are non-commercial (TABPFN-3.5 License v1.0).
- Official MCP server (https://docs.priorlabs.ai/agentic/mcp) and BO example exist, so a
  generic wrapper or "TabPFN for BO" is not novel.

## Initial ideas (brainstorm)
| Idea | Pitch | Main risk |
|---|---|---|
| Alien Pinball | agent learns hidden game physics from shots, picks next shot | discontinuous collisions; demo-heavy |
| Pocket Self-Driving Lab | replay real HTE reaction yields (Buchwald–Hartwig), pick next experiment | prior TabPFN-BO / active-learning work |
| Agent Forklift | predict which intervention rescues a failing coding agent | needs branched interventional data |
| Taste Synth | learn musical taste from pairwise choices | needs real users for evidence |
| Bug Aquarium | choose test inputs that expose hidden bugs | toy-benchmark risk |
| Grid Garden | probabilistic forecasts → battery control in CityLearn | little forecast-dependent headroom |
| The Cost of Knowing | choose which feature to acquire next | needs conditional value models |

User shortlisted Agent Forklift, Grid Garden, and a search/retrieval idea (see
02-idea-evaluations.md), then chose the retrieval idea ("Lens").
