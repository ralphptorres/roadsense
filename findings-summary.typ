#set document(title: "roadsense - Speed Safety Score: Findings Summary")
#set page(margin: 2.2cm, numbering: "1")
#set text(font: "New Computer Modern", size: 10.5pt)
#set heading(numbering: "1.")
#set par(justify: true)
#set cite(style: "ieee")

#align(center)[
  #text(size: 18pt, weight: "bold")[roadsense - Speed Safety Score]

  #text(size: 12pt)[Findings Summary and Recommended Interventions]

  #v(0.2cm)
  #text(size: 10pt)[Ralph Torres]

  #text(size: 9.5pt, style: "italic")[Limit Check]

  #text(size: 9pt)[ADB "AI for Safer Roads" Innovation Challenge]

  #text(size: 9pt)[July 5, 2026]
]

#v(0.3cm)

#align(center)[#box(width: 90%)[
  *Abstract.* Posted speed limits in Thailand and Maharashtra are frequently misaligned
  with what road conditions can safely support, but not always in the direction
  policymakers might expect. We built a Speed Safety Score (SSS) across 11,134 monitored
  road segments in Thailand and 3,577 in Maharashtra, grounded in the Safe System framework
  and a physics-based power-law risk model, that identifies not just where a posted limit
  is unsafe but why, so the recommended fix differs by segment. We flag 228 segments in
  Thailand (2.0%) and 137 in Maharashtra (3.8%) as statistically significant Speed-Unsafe
  Segments. In both countries the dominant recommended intervention is enforcement or
  traffic calming, not sign changes, an unintuitive finding with direct budget implications.
]]

#v(0.2cm)

= Introduction

The challenge asks whether posted speed limits are appropriate for their road context, not
whether drivers currently obey them. The two are related but distinct: a segment can have a
low rate of speeding while still posting a limit that is unsafe by Safe System standards,
and vice versa. This distinction motivates our entire methodology and is the source of the
paper's central finding: a naive "misalignment" narrative implies limits are wrong and
should be lowered, but our diagnostic shows this is the *minority* case in both countries.

= Methodology

Our pipeline layers four signals into a single composite score, each targeting a distinct,
named failure mode rather than a single opaque model.

*Layer 1, Safe System Gap.* Each segment's `RoadClass` × `LandUse` combination maps to a
Safe System survivable-speed threshold @who2008, e.g. 30 km/h for urban secondary roads with
pedestrian mixing, 100 km/h for access-controlled motorways. Rather than a linear gap, we
score risk as a power-law ratio
$ "SSG" = (v_"posted" / v_"threshold")^n $
following the Power Model of speed and crash severity @elvik2004, with $n=4$ (fatal-crash
exponent) for pedestrian-conflict cells and $n=2$ (injury-crash exponent) elsewhere. Crash
energy scales with $v^2$ and fatality risk climbs steeply with impact speed, so a road
posted 20% over its safe threshold is meaningfully more dangerous than a linear model would
suggest, not just 20% worse.

*Layer 2, expected operating speed.* A RandomForest regression predicts each segment's
85th-percentile operating speed from road context alone (`RoadClass`, `LandUse`, length,
traffic volume), deliberately excluding the posted limit, so the residual (actual minus
predicted) is informative about whether drivers are responding to road design or ignoring
it. Held-out R² is modest (0.39 Thailand, 0.43 Maharashtra) given the limited feature set
available, we report this honestly rather than overstate precision. Every prediction uses
genuine out-of-fold cross-validation, and each prediction's reliability is weighted by the
RandomForest's own ensemble variance (agreement across its 300 trees) rather than a coarse
sample-size cutoff. This discount is what keeps a handful of data-thin road classes (e.g.
Maharashtra's 26-segment motorway class) from distorting the score.

*Layer 3, peer comparison.* Segments are grouped into peer cohorts (road class, land use,
local population-density tier), and each segment's posted limit is compared against its
peers' typical limit, surfacing outlier postings that a purely absolute threshold would
miss. This layer's peer cohorts also supply the reference statistics the significance test
in Layer 4 uses, and the outlier finding itself is surfaced as a reported reason alongside a
flagged segment, even though it is not summed into the numeric score directly, see below.

*Layer 4, composite score and classification.* The Safe System Gap and operating-speed
residual combine into a single 0-100 Speed Safety Score via z-scored components, not
independently percentile-ranked components, which we found compresses the top of the
distribution into an indistinguishable plateau, modulated by a vulnerable-user-exposure
(VUE) multiplier built from land use, traffic volume, and two open data layers:
OpenStreetMap points of interest (schools, hospitals, markets) and WorldPop population
density, sourced per the challenge FAQ's own suggestion that `LandUse` alone is too coarse an
exposure proxy. A segment is flagged as statistically significant when its score exceeds its
Layer-3 peer cohort's own mean by more than two standard deviations, with a minimum
cohort-size floor so a small peer group's noisy statistics cannot trigger a false flag. The
continuous score and the significance flag combine into a four-tier classification, *Low*,
*Moderate*, *High*, *Critical*, rather than leaving the audience to interpret a bare number:
Critical and High require statistical significance (the misalignment is real, not peer-group
noise), Critical additionally requires a score in the top decile.

*Validation.* No crash records exist for either country, so, following the same logic used
in the surrogate-safety-measure literature @prisma2023, we benchmark the score against
expected trends rather than a held-out ground truth: (1) internal consistency, flagged
segments score far higher than unflagged ones (mean SSS 78-94 vs. 49-50), (2) concentration
of the highest-risk segments in exactly the road categories Safe System doctrine predicts
(urban secondary/pedestrian-conflict roads), (3) a weak-but-present correlation with
independent speeding-behavior fields never used in scoring, deliberately weak, since a
strong correlation would mean we were just re-measuring compliance rather than
limit-appropriateness. Connected-vehicle research supports treating a purely kinematic,
non-crash surrogate as a legitimate crash-risk indicator @hbe2026, reinforcing this
approach.

= Results

#table(
  columns: (auto, auto, auto),
  align: (left, center, center),
  table.header([*Metric*], [*Thailand*], [*Maharashtra*]),
  [Segments analyzed], [11,134], [3,577],
  [Flagged Speed-Unsafe (significant)], [228 (2.0%)], [137 (3.8%)],
  [Median SSS, flagged segments], [75.7 / 100], [92.3 / 100],
  [Mean stopping-distance excess, flagged], [+52.5 m], [+42.3 m],
  [Recommended: lower the limit only], [17 (7%)], [26 (19%)],
  [Recommended: road redesign], [68 (30%)], [45 (33%)],
  [Recommended: enforcement / calming], [142 (62%)], [66 (48%)],
  [Also high vulnerable-user exposure], [53 (23%)], [54 (39%)],
  [Classification: Critical], [35 (0.3%)], [115 (3.2%)],
  [Classification: High], [193 (1.7%)], [22 (0.6%)],
  [Classification: Moderate], [5,343 (48.0%)], [1,652 (46.2%)],
  [Classification: Low], [5,563 (50.0%)], [1,788 (50.0%)],
)

*Enforcement, not signage, is the majority fix in both countries.* This is the single most
policy-relevant finding. Our diagnostic shows that in 48-62% of flagged cases, the posted
limit is broadly acceptable but actual driving speed exceeds it, a behavior or road-design
problem, not a signage problem. Conflating these would misdirect budget toward the wrong
fix.

*Maharashtra's flagged segments are more concentrated and more severe* (median flagged SSS
92.3 vs. 78.1, despite a smaller absolute count), consistent with sparser, lower-quality
road infrastructure data producing fewer but starker outliers once the pipeline's
reliability gates (minimum peer-group size, ensemble-confidence weighting) are applied. This
is the scalability story the challenge asks for: the same methodology, unmodified, degrades
toward a smaller but higher-confidence flagged set in the data-sparse country, rather than
failing or producing noise.

*Vulnerable-user exposure compounds the risk* for roughly a quarter to two-fifths of flagged
segments. These should be treated as more urgent than their SSS alone indicates, since a
misaligned limit near a school or market carries different stakes than the same
misalignment on a low-pedestrian corridor.

= Additional physics and statistical checks

Beyond the four-layer score, we implemented three further checks that produced working
results rather than remaining theoretical.

*Stopping-distance reinterpretation.* Layer 2's residual is re-expressed in physical units
using the AASHTO stopping-sight-distance formula ($t_r = 2.5$ s perception-reaction time,
$a = 3.4$ m/s² deceleration, both standard highway-design constants, not fitted to this
data). The "stopping-distance excess" reported in Table 1 (Mean +52.5 m Thailand, +42.3 m
Maharashtra for flagged segments) converts an abstract km/h residual into a concrete,
policy-legible quantity: how many extra metres a driver needs to stop safely at the speed
this road actually produces, versus what its design predicts.

*Extreme Value Theory tail-risk modeling.* We fit a Generalized Pareto Distribution to the
upper tail of the composite risk index (peaks-over-threshold method, the same class of
technique used for crash-probability tail estimation in the surrogate-safety literature) to
estimate how extreme misalignment risk could get beyond the observed range. Thailand's
extrapolated and empirical 99.9th-percentile risk estimates agree within 1%, a good
practical validation of the fit. The fit formally fails a Kolmogorov-Smirnov goodness-of-fit
test in both countries, a known artifact of that test's sensitivity at our sample sizes
rather than evidence the tail model is wrong, so we report the result but do not lean on it
as a rigorously validated statistical guarantee.

*Street-level validation via Mapillary map features.* For the statistically significant
flagged segments (228 Thailand, 137 Maharashtra), we queried Mapillary's map features API
for nearby regulatory speed-limit signage and pedestrian-crossing infrastructure, a real,
independently-sourced check against the fields already used in scoring. Coverage was far
sparser in Maharashtra (12.4% of flagged segments had any nearby imagery) than Thailand
(39.5%), consistent with the same data-sparsity pattern already documented in the network
centrality and validation checks. Readable speed-limit signage was rare even where imagery
existed, a genuine negative result we report rather than omit. The one segment where a
sign was found is notable: a Maharashtra segment posted at 60 km/h has an actual street
sign reading 30 km/h nearby, alongside 5 pedestrian-crossing features, a single concrete,
independently-sourced instance of the exact posted-limit misalignment this project is built
to detect.

= Recommended interventions

- *Enforcement / traffic-calming (majority category)*: speed cameras, physical traffic
  calming (speed humps, chicanes, narrowed lanes), or targeted police enforcement on
  segments where the limit itself looks reasonable but is routinely exceeded.
- *Road redesign*: segments where both the posted limit and actual driving speed exceed the
  Safe System threshold. A new sign will not fix this, the physical design (lane width,
  sightlines, lack of median separation) is inviting unsafe speeds regardless of what's
  posted.
- *Lower the posted limit (sign-only)*: the smallest category in both countries, segments
  where drivers are already driving close to a safe speed, so the posted limit is the only
  thing out of alignment.
- *Priority multiplier*: within any category, segments with high vulnerable-user exposure
  (schools, markets, dense population nearby) should be resequenced ahead of otherwise
  similarly-scored segments.

= Limitations and future work

- *No crash ground truth exists* for either country, validation is necessarily trend-based,
  not outcome-based. We are explicit about this rather than implying a stronger empirical
  guarantee than the data supports.
- *`LandUse` is a coarse, GRUMP-derived urban/rural estimate* (per the challenge FAQ's own
  caveat). We supplemented it with OpenStreetMap POI density and WorldPop population density
  (VUE tier 2), but a genuinely continuous exposure signal for Thailand (Maharashtra has
  one, `UrbanPC`) would strengthen this further.
- *Street-level visual features* (Mapillary imagery, vision-language model extraction of
  sidewalks, crossings, and road width) were scoped as a further enrichment tier but not
  implemented in this submission window. The SAGAI workflow @sagai2025 is a concrete,
  citable path to this, prioritizing binary/categorical visual prompts over continuous ones
  per that paper's own accuracy findings.
- *Network-topology centrality was explored and found not usable*: the provided road
  segments form a simplified, sampled set of monitored links rather than a complete street
  network (72-83% of segments in our own constructed graph had zero betweenness due to
  fragmentation, varying by country), so this avenue was abandoned rather than reported as a
  false positive.

= Conclusion and replicability

The pipeline is built entirely from fields present in the provided datasets plus two open,
globally available enrichment sources (OpenStreetMap, WorldPop), with no country-specific
tuning beyond the Safe System threshold table itself, which is derived from WHO/OECD
doctrine rather than local calibration. Applying this methodology to a new country requires
only: (1) the same TomTom-style probe/speed-limit dataset structure, (2) a RoadClass ×
LandUse Safe System threshold table, reusable as-is since it is policy-derived rather than
data-fitted, and (3) an OpenStreetMap and WorldPop extract for the region, both free and
global in coverage. The headline result, that enforcement rather than signage is the
majority fix, is itself a replicable hypothesis other countries can test against their own
data.

#bibliography("refs.bib", title: "References", style: "ieee")
