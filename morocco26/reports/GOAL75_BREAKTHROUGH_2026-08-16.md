# MOROCCO//26 — GOAL75 breakthrough record

**Goal:** continue until scientifically-gated completion reaches 75% **or** a significant evidenced breakthrough occurs.  
**Resolution:** breakthrough reached; 75% deliberately not claimed.  
**Scientifically-gated completion after breakthrough:** 43%.  
**Forecast status:** BLOCKED.

## Breakthrough

The previous architecture treated missing constituency-level registered-voter denominators as blocking all territorial progress. That was too coarse. The project now separates two evidence gates:

1. **Seat Margin / vote-rank diagnostic** — measures the raw vote gap between the Nth list and the N+1th list and checks the top-N winner set against independent elected-list evidence. This does **not** require the registered-voter denominator and is explicitly labelled `VOTE_RANK_DIAGNOSTIC_NOT_LEGAL_ALLOCATION`.
2. **Exact legal-quota replay** — reproduces the statutory registered-voter quotient and largest-remainder allocation. This **does** require constituency registered-voter denominators and remains a separate strict gate.

This removes an artificial blocker without weakening the legal audit.

## Evidence produced

- Development Seat Margin panel expanded from 4 pilot constituencies to **47 local constituencies**.
- The development panel spans **all 12 regions**.
- A **12-constituency territorial holdout was sealed before its 2021 outcomes were extracted in this run**. It remains excluded from parameter tuning.
- 33 local constituencies remain unextracted outside the sealed holdout.
- A scalable secondary acquisition path was identified: individual constituency result pages expose the 2021 vote table and, on many checked pages, registered and expressed totals. Exact legal replay still requires extraction and reconciliation.
- **61/61 repository tests pass** after the architecture and evidence changes.

## Political finding: seat vulnerability is extremely heterogeneous

Among the 47 development constituencies, nine have a raw last-seat margin of **500 votes or less**:

| Constituency | Last winner | First nonwinner | Raw gap |
|---|---|---|---:|
| Agadir Ida-Outanane | PPS | USFP | **12** |
| Es-Semara | PAM | RNI | **16** |
| Guelmim | RNI | PI | **34** |
| Rabat-Océan | MP | PJD | **271** |
| Tan-Tan | RNI | PI | **288** |
| Fès-Sud | USFP | PJD | **367** |
| Salé-Médina | MP | PI | **434** |
| Rabat-Chellah | USFP | PI | **440** |
| Oujda-Angad | USFP | PJD | **448** |

The development-panel median is **3,452 votes**, while observed raw gaps range from **12** to more than 16,000 votes. A national swing of identical size therefore has radically different seat implications depending on territory.

## Why this changes the project

The correct live-2026 primitive is not simply national party popularity. It is a territorial state variable:

`local baseline + candidate/network change + turnout regime + event exposure + distance to seat cutoff`

This is exactly the empirical substrate required before Model D / AgentSociety can be judged. The holdout is now protected against retrospective tuning, and B/C must be frozen before D sees it.

## What is still NOT proven

- The 47-constituency vote-rank panel is not an exact legal replay of all seats.
- The 12 holdout outcomes have not been used for tuning and must remain sealed until B/C are frozen.
- Model D has not yet demonstrated out-of-sample value.
- No national 2026 forecast is unlocked.

## Next gates

1. Finish 92/92 Seat Margin coverage while preserving the sealed holdout protocol.
2. Extract/reconcile registered-voter denominators and complete exact legal replay.
3. Freeze B/C predictions and metrics before opening the territorial holdout.
4. Run Model D against the same holdout; **kill D if it does not beat B and C stably out of sample**.
5. Only then scale the live 2026 event-to-seat mechanism engine.
