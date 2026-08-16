# MOROCCO//26 — Goal100 P0 Resolution

**As of:** 2026-08-16 20:44 Africa/Casablanca  
**Branch:** `morocco26-goal100-p0`  
**Purpose:** remove the six P0 scientific ambiguities that prevented a defensible prospective territorial forecast, without pretending that unexecuted calibration work is complete.

## Executive result

The six original P0 questions no longer contain an unresolved conceptual choice. They reduce to three implementation dependencies:

1. **Legal/geometry certification:** authoritative geometry diff + regression of the new fail-closed 2026 allocator.
2. **Empirical panel:** clean 2011/2016/2021 ingestion/harmonization + a 2026 local-electorate posterior constrained to the official national roll.
3. **Forecast fit:** retrospective temporal scoring to select B*, then fit/calibrate the hierarchical uncertainty model and Monte Carlo seat distribution.

An immutable **F-1** can be emitted before full calibration if and only if it is labelled `EXPERIMENTAL_PRECALIBRATION`. **F0 is preliminary, not final.** Later F1/F2/... snapshots may incorporate newly available information, but no prior snapshot can be rewritten.

---

## P0-1 — Electoral geometry

### Resolution

The current consolidated Organic Law 27.11 keeps the House at **395 seats: 305 local + 90 regional**. Article 1 specifies the 12 regional magnitudes. Article 2 provides for local constituencies and magnitudes by decree. The House's current election-law page still lists **Decree 2.11.603 of 19 October 2011** as the decree creating local constituencies and assigning their seats. The repo's current geometry is 92 local constituencies / 305 seats.

**Status:** `RESOLVED_WITH_LEGAL_WATCH`.

### Remaining gate

Machine-diff the repo 92-row map against the authoritative decree/House table and run the same source watch before every forecast snapshot. A later official decree is the only fact that invalidates this decision.

---

## P0-2 — Legal votes-to-seats allocator

### Resolution

Current Article 84 is explicit:

- quotient = **registered voters / district seats**;
- remaining seats by **largest remainders**;
- candidate seats follow list order;
- a binding exact remainder tie is resolved by the **youngest eligible next candidate**, then **lottery** on equal age;
- a one-member election uses plurality, with the same age/lottery tie-break;
- a unique list/candidate needs at least **one fifth of registered voters**.

Article 85 applies the Article-84 method to regional allocation.

### Goal75 defect discovered

The Goal75 helper `alloc()` used `(-remainder, -votes, party_name)` as the ordering key. The `-votes, party_name` fallback is not the statutory tie-break. This does not invalidate the frozen Goal75 comparative experiment, but it is unacceptable for a legally exact Goal100 forecast.

### Patch

Added:

- `src/morocco26/legal_allocator_2026.py`
- `scripts/goal100_legal_allocator_selftest.py`

The new allocator uses integer-exact arithmetic and **fails closed** when a statutory age/lottery tie cannot be resolved from evidence. It does not silently invent a winner.

**Status:** `LEGAL_RULE_RESOLVED_CORE_PATCH_IMPLEMENTED_REGRESSION_PENDING`.

### Remaining gate

Replay the clean historical vectors through the new allocator. Binding exact ties must either have candidate-age evidence or remain explicitly unresolved.

---

## P0-3 — Registered-voter denominator N

### Resolution

The official electoral-roll portal reports **15,801,162 registered voters**, situation closed **10 July 2026** after the exceptional revision. The national total is therefore no longer unknown.

A complete official indexed **92-local N table** has not been found. The scientifically correct treatment is not to fabricate it and not to block the entire forecast.

### Forecast treatment

Let `N_1 ... N_92` be a positive-integer latent vector constrained by:

```text
sum(N_c) = 15,801,162 exactly
```

Construct its posterior from the strongest historical electorate/population anchors and observed roll changes. Each Monte Carlo election samples one coherent local-N vector; regional N is the deterministic sum of local N in the region. Article 84 is then exact **conditional on that draw**. Published seat probabilities marginalize over N uncertainty.

Required label until official local N becomes available:

`OFFICIAL_NATIONAL_CONSTRAINED_LOCAL_POSTERIOR`

A later snapshot may collapse this uncertainty when authoritative local N is obtained; earlier snapshots remain immutable.

**Status:** `NATIONAL_EXACT_LOCAL_LATENT_AND_MARGINALIZED`.

---

## P0-4 — Historical calibration panel

### Resolution

TAFRA explicitly publishes legislative-election datasets for **2002, 2007, 2011, 2016 and 2021**, and states that its datasets use common geographic/person identifiers. The core modern local calibration panel should use **2011 → 2016 → 2021**, with older years used only where a validated geographic crosswalk exists.

Critical caveat: TAFRA documents that the Interior Ministry did **not** publish 2016 registered-voter counts by legislative constituency. Its 2020 exercise therefore used voting-age population or 2011 registered counts as approximations. Goal100 must preserve this uncertainty; it must not manufacture exact 2016 turnout denominators.

Historical data calibrates **vote-share transitions / residual uncertainty**. Historical seat rules are not transplanted into 2026: all prospective 2026 vote draws go through the current 2026 allocator.

The existing Goal75 web-table acquisition cannot be treated as clean calibration truth where its parsing produced contradictory coverage fields.

**Status:** `SOURCE_PATH_RESOLVED_CLEAN_INGEST_PENDING`.

---

## P0-5 — Selecting B* without leakage

### Resolution

The 12-territory Goal75 holdout has been opened and scored. It is scientifically useful evidence, but it is **consumed** and therefore cannot be reused to tune Goal100 and then be described as untouched.

Freeze a small non-agentic candidate family:

- **B0** — persistence + national historical swing; separate turnout.
- **B1** — hierarchical national + regional + local structural state model.
- **B2** — B1 + structured non-agentic candidate/network/event covariates; unestimated narrative effects shrink to zero.
- **Bstack** — optional convex/stacked combination whose weights are learned only from retrospective temporal predictions.

Selection uses prequential temporal predictions:

```text
fit <= 2011  -> predict 2016
fit <= 2016  -> predict 2021
```

Earlier transitions enter only if the geographic crosswalk passes. These are retrospective temporal validations, not pristine secret holdouts. The **2026 election is the decisive untouched temporal test**.

`B*` means the best member of this preregistered family under a preregistered proper score, not an unbounded claim of global optimality.

**Status:** `SELECTION_PROTOCOL_RESOLVED_FIT_PENDING`.

---

## P0-6 — Predictive uncertainty and territorial dependence

### Resolution

Independent district noise is unacceptable, and a free 92×92 covariance matrix is unidentifiable from the available modern transitions.

Use a hierarchical compositional state model. For party shares, model transformed composition with:

```text
national party swing
+ regional party shock
+ local residual
+ structured non-agentic covariates
```

Shared national/regional factors create coherent territorial dependence. Use strong shrinkage / low-rank structure rather than hundreds of free correlations.

Model turnout separately on the logit scale with national/regional/local components. Only introduce turnout–party correlation if historical evidence identifies it.

Each Monte Carlo draw must be **one coherent election**:

1. national party swing;
2. regional shocks;
3. local residuals;
4. turnout;
5. constrained local-N vector if local N remains latent;
6. structured non-agentic evidence effects;
7. integer vote counts;
8. exact Article-84 local and regional allocations;
9. national 395-seat aggregation.

Temporal hindcasts calibrate a small number of variance scales and interval coverage. Variance floors prevent false precision.

This is consistent with established Bayesian multiparty forecasting work that models party support compositionally and produces posterior probabilities, and with dynamic hierarchical election models that borrow strength across electoral units.

**Status:** `ARCHITECTURE_RESOLVED_PARAMETERS_PENDING`.

---

# Consequence for the agentic experiment

Do **not** revive Model D voter agents. Freeze B* first, then decompose agentic value:

- `E_collect`: additional timestamped fact acquisition; deterministic downstream mapping.
- `E_reason`: exactly the B2 corpus; bounded agentic residual reasoning.
- `E_full`: acquisition + residual reasoning.

The estimands are therefore separable:

```text
collection alpha = E_collect - B2
reasoning alpha  = E_reason  - B2
total alpha      = E_full    - B2
```

No agentic output receives predictive credit before its combination/residual protocol is frozen prospectively.

---

# Forecast snapshot rule

F0 is not privileged or final. The research value comes from the **sequence of immutable ex-ante forecasts**.

Minimum metadata for every snapshot:

- data cutoff and creation timestamp;
- source-manifest hash;
- git commit / model hash / legal-spec hash;
- electorate-N state (`official` vs constrained posterior);
- calibration state;
- random-seed manifest;
- 92 local probability distributions;
- 12 regional probability distributions;
- national 395-seat distribution.

A later snapshot may improve the model/data only under the preregistered update policy. It creates a new forecast; it never rewrites history.

---

# Remaining execution order

### Gate A — legal + geometry

Run authoritative 92/305 + 12/90 diff and 104-vector legal regression with the new allocator.

### Gate B — empirical panel + electorate

Ingest/harmonize TAFRA 2011/2016/2021; construct the national-constrained local-N posterior and quantify allocator sensitivity to N.

### Gate C — B* + uncertainty

Run temporal hindcasts, select B*, fit the hierarchical variance/correlation structure, run posterior predictive checks, then emit the earliest properly labelled immutable probability snapshot.

**Scientific conclusion:** the original six P0 questions have been converted from ambiguous blockers into explicit machine-testable contracts. The project is no longer waiting for a conceptual answer; it is waiting for three bounded execution gates.
