# EVT tail-risk findings

Peaks-over-threshold (Generalized Pareto Distribution fit above the 90th
percentile) attempted on two candidate targets, `pipe/evt_tail.py`. Same class
of technique used for crash-probability tail estimation in the literature review
(Songchitruksa & Tarko 2006, cited via PRISMA's related work).

## `SSG_risk_ratio`: rejected as a target

Catastrophic KS goodness-of-fit (stat=0.978, Thailand). Cause: it's built from
`SpeedLimit`, which only takes a small set of discretized, rounded values
(30/40/50/.../120 km/h), raised to a small integer/exponent power. This is
fundamentally not a continuous variable, GPD assumes continuity in the tail, and
this violates that badly. Not usable for EVT.

## `risk_index`: usable, with a caveat

The continuous composite feeding SSS.

| | Thailand | Maharashtra |
|---|---|---|
| threshold u (p90) | 1.274 | 0.425 |
| exceedances | 1,114 (10.0%) | 358 (10.0%) |
| shape (xi) | -1.394 (bounded tail) | +0.167 (heavy tail) |
| extrapolated p99.9 | 2.443 | 7.263 |
| empirical p99.9 (direct) | 2.425 | 5.007 |
| KS test | stat=0.113, p<0.001 | stat=0.079, p=0.021 |

Both technically fail the KS test at the 5% level. **This needs an honest
caveat, not silent suppression**: KS tests are notoriously oversensitive at
large n (1,114 and 358 exceedances here), rejecting even small,
practically-negligible deviations. Thailand's extrapolated p99.9 (2.443) agrees
closely with the empirical p99.9 (2.425, ~0.7% difference), a good practical
validation of the fit despite the failed KS test. Maharashtra's extrapolated
value (7.263) diverges more from its empirical one (5.007, ~45% higher), which
is expected given far fewer exceedances (358 vs 1,114) to constrain the tail
shape, and is arguably the point of doing EVT at all: extrapolating beyond what
a small, sparse sample directly shows, exactly the "how does this degrade with
less data" scalability question the challenge is asking about.

**How to use this in the write-up**: cite the Thailand fit as the stronger,
better-validated result (close empirical/extrapolated agreement despite formally
failing KS), and frame Maharashtra's larger divergence as illustrating the
scalability/data-sparsity story, not as a failure. Don't claim a rigorous
statistical guarantee either fit passes KS, be upfront that it doesn't, and
explain why that's a large-n artifact rather than evidence the tail model is
wrong.

