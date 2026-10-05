## Test split (frozen, run once)

```
120 users (common to all learners); like rate among rated papers 0.597

             learner  users   auc   p@1  ndcg@3  prec_top25  brier   ece  gate_prec  gate_cov
        rocchio:g0.5    120 0.724 0.848   0.931       0.821    NaN   NaN        NaN       NaN
       embsig:tabpfn    120 0.718 0.850   0.938       0.822  0.190 0.154      0.843     0.330
   embsig:tabpfnfast    120 0.714 0.851   0.936       0.821  0.191 0.158      0.826     0.359
embsig:logistic+C0.1    120 0.708 0.850   0.932       0.813  0.208 0.185      0.815     0.402
  emb:logistic+C0.03    120 0.696 0.845   0.931       0.802  0.208 0.179      0.829     0.289
         embsig:lgbm    120 0.669 0.843   0.925       0.778  0.258 0.256      0.761     0.506
        roc:logistic    120 0.605 0.828   0.912       0.757  0.217 0.179      0.842     0.210

Paired over users: TabPFN learner minus best baseline (95% bootstrap CI)
  auc       embsig:tabpfn          vs rocchio:g0.5         -0.0052 [-0.0256,+0.0164] better for 50/118 users
  auc       embsig:tabpfnfast      vs rocchio:g0.5         -0.0097 [-0.0308,+0.0108] better for 49/118 users
  p@1       embsig:tabpfn          vs embsig:logistic+C0.1 +0.0001 [-0.0093,+0.0093] better for 21/120 users
  p@1       embsig:tabpfnfast      vs embsig:logistic+C0.1 +0.0007 [-0.0082,+0.0095] better for 21/120 users
  ndcg@3    embsig:tabpfn          vs embsig:logistic+C0.1 +0.0058 [-0.0002,+0.0121] better for 55/120 users
  ndcg@3    embsig:tabpfnfast      vs embsig:logistic+C0.1 +0.0036 [-0.0023,+0.0097] better for 49/120 users
  prec_top25 embsig:tabpfn          vs rocchio:g0.5         +0.0014 [-0.0168,+0.0208] better for 39/120 users
  prec_top25 embsig:tabpfnfast      vs rocchio:g0.5         +0.0004 [-0.0184,+0.0191] better for 39/120 users
  brier     embsig:tabpfn          vs emb:logistic+C0.03   -0.0177 [-0.0241,-0.0119] better for 87/120 users
  brier     embsig:tabpfnfast      vs emb:logistic+C0.03   -0.0171 [-0.0237,-0.0113] better for 87/120 users
  ece       embsig:tabpfn          vs emb:logistic+C0.03   -0.0245 [-0.0367,-0.0133] better for 70/120 users
  ece       embsig:tabpfnfast      vs emb:logistic+C0.03   -0.0207 [-0.0330,-0.0089] better for 71/120 users

== embsig:tabpfnfast
  H1 brier vs roc:logistic           -0.0261 [-0.0340, -0.0186] n=120  below 0
  H1 brier vs emb:logistic+C0.03     -0.0171 [-0.0238, -0.0111] n=120  below 0
  H1 brier vs embsig:logistic+C0.1   -0.0173 [-0.0226, -0.0125] n=120  below 0
  H1 brier vs embsig:lgbm            -0.0668 [-0.0771, -0.0576] n=120  below 0
  H1 overall: SUPPORTED
  H2 ece   vs roc:logistic           -0.0213 [-0.0365, -0.0072] n=120  below 0
  H2 ece   vs emb:logistic+C0.03     -0.0207 [-0.0336, -0.0088] n=120  below 0
  H2 ece   vs embsig:logistic+C0.1   -0.0269 [-0.0373, -0.0171] n=120  below 0
  H2 ece   vs embsig:lgbm            -0.0980 [-0.1110, -0.0852] n=120  below 0
  H2 overall: SUPPORTED
  H3 auc   vs rocchio:g0.5            -0.0097 [-0.0314, +0.0112] n=118  non-inferiority (lower > -0.02): NOT supported
== embsig:tabpfn
  H1 brier vs roc:logistic           -0.0267 [-0.0343, -0.0192] n=120  below 0
  H1 brier vs emb:logistic+C0.03     -0.0177 [-0.0240, -0.0122] n=120  below 0
  H1 brier vs embsig:logistic+C0.1   -0.0179 [-0.0229, -0.0129] n=120  below 0
  H1 brier vs embsig:lgbm            -0.0674 [-0.0776, -0.0583] n=120  below 0
  H1 overall: SUPPORTED
  H2 ece   vs roc:logistic           -0.0251 [-0.0392, -0.0112] n=120  below 0
  H2 ece   vs emb:logistic+C0.03     -0.0245 [-0.0365, -0.0131] n=120  below 0
  H2 ece   vs embsig:logistic+C0.1   -0.0307 [-0.0403, -0.0217] n=120  below 0
  H2 ece   vs embsig:lgbm            -0.1018 [-0.1148, -0.0889] n=120  below 0
  H2 overall: SUPPORTED
  H3 auc   vs rocchio:g0.5            -0.0052 [-0.0255, +0.0151] n=118  non-inferiority (lower > -0.02): NOT supported
```

## Dev split (iteration 3, used for design decisions)

```
120 users (common to all learners); like rate among rated papers 0.598

             learner  users   auc   p@1  ndcg@3  prec_top25  brier   ece  gate_prec  gate_cov
        rocchio:g0.5    120 0.756 0.852   0.943       0.840    NaN   NaN        NaN       NaN
   embsig:tabpfnfast    120 0.746 0.852   0.944       0.825  0.183 0.148      0.842     0.348
       embsig:tabpfn    120 0.744 0.848   0.942       0.819  0.184 0.147      0.840     0.327
embsig:logistic+C0.1    120 0.732 0.860   0.944       0.821  0.200 0.176      0.813     0.407
          emb:tabpfn    120 0.732 0.849   0.940       0.804  0.198 0.160      0.858     0.262
  emb:logistic+C0.03    120 0.730 0.858   0.942       0.807  0.201 0.168      0.845     0.297
         embsig:lgbm    120 0.692 0.833   0.928       0.789  0.242 0.238      0.767     0.523
          sig:tabpfn    120 0.673 0.836   0.921       0.795  0.193 0.152      0.859     0.320
         feat:tabpfn    120 0.662 0.830   0.920       0.798  0.191 0.147      0.876     0.311
      sig:tabpfnfast    120 0.662 0.832   0.921       0.800  0.194 0.154      0.849     0.324
        sig:logistic    120 0.656 0.834   0.919       0.790  0.201 0.165      0.838     0.349
       feat:logistic    120 0.648 0.826   0.917       0.796  0.209 0.175      0.803     0.403
            sig:lgbm    120 0.621 0.830   0.914       0.772  0.239 0.230      0.769     0.479
           feat:lgbm    120 0.619 0.817   0.910       0.775  0.255 0.253      0.737     0.531
        roc:logistic    120 0.615 0.824   0.912       0.767  0.209 0.174      0.877     0.231

Paired over users: TabPFN learner minus best baseline (95% bootstrap CI)
```

## Exploratory baselines added after the test (not pre-registered)

Calibrated logistic (sklearn CalibratedClassifierCV, sigmoid), corrected Platt-calibrated
Rocchio, the user's own like rate, and the product's no-age variant, on the same test users.

```
120 users (common to all learners); like rate among rated papers 0.597

                  learner  users   auc   p@1  ndcg@3  prec_top25  brier   ece  gate_prec  gate_cov
             rocchio:g0.5    120 0.724 0.848   0.931       0.821    NaN   NaN        NaN       NaN
            rocplatt:g0.5    120 0.724 0.848   0.931       0.788  0.203 0.177      0.807     0.283
            embsig:tabpfn    120 0.718 0.850   0.938       0.822  0.190 0.154      0.843     0.330
   embsignoage:tabpfnfast    120 0.717 0.849   0.935       0.825  0.191 0.159      0.826     0.356
        embsig:tabpfnfast    120 0.714 0.851   0.936       0.821  0.191 0.158      0.826     0.359
     embsig:logistic+C0.1    120 0.708 0.850   0.932       0.813  0.208 0.185      0.815     0.402
embsignoage:logistic+C0.1    120 0.707 0.850   0.932       0.812  0.208 0.187      0.813     0.400
       embsig:logcal+C0.1    120 0.703 0.842   0.932       0.801  0.201 0.171      0.856     0.169
       emb:logistic+C0.03    120 0.696 0.845   0.931       0.802  0.208 0.179      0.829     0.289
         emb:logcal+C0.03    120 0.693 0.839   0.929       0.785  0.207 0.178      0.811     0.147
            emb:logcal+C1    120 0.685 0.836   0.927       0.770  0.209 0.177      0.817     0.141
              embsig:lgbm    120 0.669 0.843   0.925       0.778  0.258 0.256      0.761     0.506
             roc:logistic    120 0.605 0.828   0.912       0.757  0.217 0.179      0.842     0.210
            prior:laplace    120 0.500 0.821   0.899       0.619  0.246 0.184      0.569     0.029

Paired over users: TabPFN learner minus best baseline (95% bootstrap CI)
  auc       embsig:tabpfn          vs rocchio:g0.5         -0.0052 [-0.0256,+0.0164] better for 50/118 users
```
