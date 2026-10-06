Exploratory re-analysis of held-out test predictions (pre-registered run; no new models).

The original `roc:logistic` baseline is distinct from the corrected, exploratory
`rocplatt:g0.5` model in the [full results](../results/feedbench.md). Threshold
coverage is pooled here; the primary results average within users. The product
does not implement background notifications.

| Model | Precision in each user's top 30% | Δ vs TabPFN-Fast (95% CI) |
|---|---|---|
| TabPFN-3.5-Fast (Lens Feed) | 0.810 | — |
| TabPFN-3.5 | 0.809 | TabPFN +0.001 [-0.005, +0.007] |
| Logistic on embeddings | 0.790 | TabPFN +0.020 [+0.006, +0.034] |
| Logistic, same inputs | 0.802 | TabPFN +0.008 [-0.005, +0.022] |
| LightGBM, same inputs | 0.768 | TabPFN +0.042 [+0.027, +0.056] |
| Rocchio-feature logistic (original baseline) | 0.766 | TabPFN +0.044 [+0.021, +0.067] |
| Rocchio (scores) | 0.811 | TabPFN -0.001 [-0.020, +0.018] |

| Model | Notified at match ≥ 0.8 | …of which liked |
|---|---|---|
| TabPFN-3.5-Fast (Lens Feed) | 35.2% | 86.9% |
| TabPFN-3.5 | 32.8% | 87.7% |
| Logistic on embeddings | 28.9% | 85.6% |
| Logistic, same inputs | 39.6% | 84.3% |
| LightGBM, same inputs | 49.1% | 78.5% |
| Rocchio-feature logistic (original baseline) | 20.7% | 87.0% |
