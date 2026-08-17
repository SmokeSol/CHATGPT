#!/usr/bin/env python3
"""Synchronize top-level Goal100 trackers after immutable F0 registration.

This script changes status/tracking surfaces only. It never edits F-1, F0,
B2 scientific artifacts, coefficients, cutoffs, or evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
AS_OF = "2026-08-17T16:22:07+01:00"
CUTOFF = "2026-08-17T16:14:58+01:00"
F1_HASH = "de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1"
F0_HASH = "fbe5197999f20d0612bc0c66e1954b5c611b11208e43a72eb5494a03b1e40d3f"
F0_REG_CERT = "40175a828eda6a33642caa7efb950d43cd99f11b0653b8c80e201a8739c52c8c"
B2_FREEZE = "eab248d63051643600d0b2220f269b587302c4631fe24a7760fd971277fd88e1"
MARKER = "F0_CHECKPOINT_2026_08_17"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_current_state() -> None:
    path = G100 / "current_state.json"
    s = load(path)
    s["schema_version"] = "1.4"
    s["as_of"] = AS_OF
    s["program_phase"] = "P7_B2_STRUCTURED_EVIDENCE_LAYER_F0_REGISTERED"
    obj = s.setdefault("goal100_objective", {})
    obj["next_forecast"] = "F1"
    obj["next_forecast_class"] = "PREREGISTERED_UPDATE"
    obj["forecast_status"] = "F0_REGISTERED_IMMUTABLE"
    obj["first_calibrated_snapshot_status"] = "F0_REGISTERED_PRELIMINARY_IDENTITY_COUNTERFACTUAL"
    obj["agentic_experiment_status"] = "E_COLLECT_PREREGISTRATION_OPEN_EXECUTION_NOT_STARTED"

    breakthroughs = s.setdefault("verified_breakthroughs", [])
    ids = {x.get("id") for x in breakthroughs}
    if "BT-B2-FROZEN" not in ids:
        breakthroughs.append({
            "id": "BT-B2-FROZEN",
            "claim": "B2 is frozen as a negative deterministic result: B2-3 is DATA_BLOCKED_NONAGENTIC, B2-4 failed authoritative roster verification, B2-5 passes on an empty admissible claim set, and all predictive coefficients remain exactly zero.",
            "evidence": "morocco26/data/goal100/b2_freeze_certificate.json"
        })
    if "BT-F0-REGISTERED" not in ids:
        breakthroughs.append({
            "id": "BT-F0-REGISTERED",
            "claim": "F0 is registered immutable as an exact identity counterfactual over the registered 50,000-election F-1 ensemble because frozen B2 admits zero mechanical constraints and zero predictive effects.",
            "evidence": "morocco26/data/goal100/f0_registration_certificate.json"
        })

    s["next_execution_order"] = [
        "preregister E_collect against the frozen B2 cutoff, source policy, 16 blocked historical input classes and 92 unresolved Arabic roster rows",
        "execute E_collect only after its protocol and scoring contract are frozen; never modify F-1 or F0",
        "then preregister E_reason on the same evidence corpus and cutoff",
        "only after independent collection and reasoning ablations are frozen may E_full open"
    ]
    anti = s.setdefault("anti_drift", {})
    anti["B2_is_frozen"] = True
    anti["F0_may_never_be_overwritten"] = True
    anti["agentic_execution_requires_preregistration"] = True
    anti["unresolved_arabic_rows_must_not_be_semantically_backfilled_into_B2_or_F0"] = True
    anti["agentic_layer_remains_locked"] = True

    s["b2"] = {
        "status": "FROZEN_NEGATIVE_RESULT",
        "evidence_cutoff": CUTOFF,
        "freeze_certificate": "morocco26/data/goal100/b2_freeze_certificate.json",
        "freeze_certificate_sha256": B2_FREEZE,
        "B2_3": "B2_3_DATA_BLOCKED_NONAGENTIC",
        "B2_4": "B2_4_FAIL",
        "B2_5": "PASS_EMPTY_ADMISSIBLE_SET",
        "B2_6": "FAIL_CLOSED_ZERO_COEFFICIENTS",
        "mechanical_constraints_admitted": 0,
        "predictive_coefficients": "ALL_EXACTLY_ZERO",
        "reserved_for_e_collect": {"historical_input_classes": 16, "unresolved_arabic_roster_rows": 92}
    }
    s["f0"] = {
        "status": "REGISTERED_IMMUTABLE_PRELIMINARY_FORECAST",
        "created_at": AS_OF,
        "data_cutoff": CUTOFF,
        "forecast_artifact_sha256": F0_HASH,
        "distribution_sha256": F1_HASH,
        "distribution_equivalence_to_F_minus_1": "EXACT",
        "counterfactual_elections": 50000,
        "mechanical_delta": "EXACT_ZERO",
        "predictive_delta": "EXACT_ZERO",
        "full_B2_delta": "EXACT_ZERO",
        "registration_certificate": "morocco26/data/goal100/f0_registration_certificate.json",
        "registration_certificate_sha256": F0_REG_CERT,
        "agentic_information_used": False
    }
    write_json(path, s)


def sync_gate_registry() -> None:
    path = G100 / "gate_registry.json"
    g = load(path)
    g["schema_version"] = "1.3"
    g["as_of"] = AS_OF
    rows = {x["id"]: x for x in g.get("agentic_unlock", [])}
    rows["B2-FROZEN"] = {
        "id": "B2-FROZEN",
        "status": "CLOSED",
        "evidence": "morocco26/data/goal100/b2_freeze_certificate.json",
        "result": "FROZEN_NEGATIVE_RESULT"
    }
    rows["E-COLLECT-PREREGISTERED"] = {
        "id": "E-COLLECT-PREREGISTERED",
        "status": "OPEN",
        "execution_status": "NOT_STARTED",
        "reason": "F0 is registered immutable; the E_collect protocol may now be preregistered against the frozen B2 cutoff and reserved corpus. Execution remains forbidden until preregistration closes."
    }
    rows["E-REASON-PREREGISTERED"] = {
        "id": "E-REASON-PREREGISTERED",
        "status": "LOCKED",
        "reason": "Keep the causal sequence: E_collect must be preregistered and evaluated before same-corpus residual reasoning opens."
    }
    rows["E-FULL-PREREGISTERED"] = {
        "id": "E-FULL-PREREGISTERED",
        "status": "LOCKED",
        "reason": "Full-agentic evaluation remains locked until collection and reasoning ablations are independently frozen."
    }
    order = ["B2-FROZEN", "E-COLLECT-PREREGISTERED", "E-REASON-PREREGISTERED", "E-FULL-PREREGISTERED"]
    g["agentic_unlock"] = [rows[x] for x in order]
    g["forecast_state"] = {
        "latest_registered_snapshot": "F0",
        "latest_status": "REGISTERED_IMMUTABLE_PRELIMINARY_FORECAST",
        "next_snapshot_id": "F1",
        "f0_registration_certificate": "morocco26/data/goal100/f0_registration_certificate.json"
    }
    write_json(path, g)


def sync_status() -> None:
    path = ROOT / "STATUS.md"
    text = f"""# MOROCCO//26 — Current Status

Canonical live tracker: `reports/GOAL100_TRACKER.md`.

Machine-readable state:

- `data/goal100/current_state.json`
- `data/goal100/gate_registry.json`
- `data/goal100/forecast_registry.json`
- `data/goal100/b2_current_state.json`
- `data/goal100/b2_gate_registry.json`

Current scientific checkpoint: **F0 REGISTERED IMMUTABLE**.

B2 is frozen as a **negative deterministic result**: `B2_3_DATA_BLOCKED_NONAGENTIC`, `B2_4_FAIL`, provenance audit PASS on an empty admissible claim set, and all predictive coefficients exactly zero. No missing or unresolved evidence was converted to absence.

F0 is the first conventional preliminary forecast milestone. Because frozen B2 admits **0 mechanical constraints** and **0 predictive effect**, F0 is an exact identity counterfactual over the registered 50,000-election F-1 ensemble. F-1 remains immutable.

Reserved controlled test material for `E_collect`: **16 historical input classes + 92 unresolved Arabic PJD roster rows**.

Agentic experiment: **execution NOT STARTED**. `E-COLLECT-PREREGISTERED` is OPEN; `E_reason` and `E_full` remain LOCKED.

Next forecast ID: **F1**. Any update must be append-only; neither F-1 nor F0 may be overwritten.

CI authority: `.github/workflows/morocco26-b2-protocol.yml` and `.github/workflows/morocco26-goal100-tracking.yml` must pass. Frozen Goal75 evidence and registered forecasts are never edited in place.
"""
    path.write_text(text, encoding="utf-8")


def sync_tracker() -> None:
    path = ROOT / "reports" / "GOAL100_TRACKER.md"
    text = path.read_text(encoding="utf-8")
    if MARKER in text:
        return
    insert = f"""
<!-- {MARKER} -->
## Current checkpoint — F0 registered (17 August 2026)

**Machine truth supersedes the historical sections below where they describe F-1 or B2 as pending.** F0 is now registered immutable.

- B2 terminal state: **frozen negative result**.
- B2-3: `B2_3_DATA_BLOCKED_NONAGENTIC` — 0.0 coverage on both historical transitions vs frozen 0.8 threshold.
- B2-4: `B2_4_FAIL` — 92 Arabic PJD rows parsed, 0 deterministically resolved/admitted; no transliteration or semantic guessing was used.
- B2-5: `PASS_EMPTY_ADMISSIBLE_SET`; zero silently bridged conflicts.
- B2-6: `FAIL_CLOSED_ZERO_COEFFICIENTS`; no ridge fit, all predictive coefficients exactly zero.
- B2-7: frozen at `{CUTOFF}`.
- F0: **REGISTERED_IMMUTABLE_PRELIMINARY_FORECAST**; exact identity counterfactual over F-1's registered 50,000 coherent elections, with mechanical/predictive/full-B2 deltas all exactly zero.
- F-1 remains immutable; F0 may never be overwritten.
- Controlled future `E_collect` test material remains untouched: 16 blocked historical input classes + 92 unresolved Arabic roster rows.
- `E_collect` execution has **not** started. Only its preregistration gate is open; `E_reason` and `E_full` remain locked.
- Next immutable forecast ID: `F1`.

Canonical certificates: `data/goal100/b2_freeze_certificate.json`, `data/goal100/forecasts/F0/simulation_certificate.json`, `data/goal100/f0_registration_certificate.json`.

---

### Historical tracker retained below

The material below is preserved as the prior project state and should not be read as the current checkpoint where it says F-1/F0/B2 are pending.

"""
    anchor = "## North star"
    if anchor in text:
        text = text.replace(anchor, insert + anchor, 1)
    else:
        text = insert + text
    text = text.replace("Last synchronized: **2026-08-16 21:30 Africa/Casablanca**.", "Last synchronized: **2026-08-17 16:22 Africa/Casablanca**.", 1)
    path.write_text(text, encoding="utf-8")


def sync_ariane() -> None:
    path = ROOT / "FIL_ARIANE.md"
    text = path.read_text(encoding="utf-8")
    marker = "Entrée A024 — Gel B2 négatif et enregistrement F0"
    if marker in text:
        return
    entry = f"""

### 2026-08-17 — Entrée A024 — Gel B2 négatif et enregistrement F0

**Question/gate traité :** fermer B2 sans déplacer les règles gelées, puis produire le snapshot prospectif `F0` avant toute expérience agentique.

**Résultat B2 :** `B2_3_DATA_BLOCKED_NONAGENTIC` et `B2_4_FAIL` sont conservés comme échecs visibles. `B2-5` passe sur un ensemble admissible vide avec zéro conflit silencieusement résolu. `B2-6` applique mécaniquement la règle de défaut : aucun fit ridge n'est exécuté et tous les coefficients prédictifs restent exactement à zéro. `B2-7` gèle le résultat négatif au cutoff `{CUTOFF}`.

**Résultat F0 :** `REGISTERED_IMMUTABLE_PRELIMINARY_FORECAST`. B2 n'admettant aucun changement mécanique et aucun effet prédictif, `F0` est l'identité exacte sur les 50 000 élections cohérentes déjà enregistrées dans `F-1`; un nouveau tirage Monte Carlo n'aurait ajouté que du bruit numérique. Les ablations mécanique, résiduelle et B2 complète ont toutes un delta `EXACT_ZERO`.

**Frontière scientifique :** `F-1` n'est pas réécrit; `F0` ne contient aucune information agentique. Les 16 classes d'entrée historiques bloquées et les 92 lignes arabes PJD non résolues restent intactes comme corpus contrôlé pour mesurer ultérieurement `Δ_collect`.

**Décision :** B2 est terminé et gelé; F0 est enregistré. `E-COLLECT-PREREGISTERED` peut maintenant s'ouvrir, mais `E_collect` n'est pas exécuté. `E_reason` et `E_full` restent verrouillés.

**Prochaine action exacte :** preregistrer `E_collect` contre le cutoff et le corpus B2 gelés, sans modifier `F-1` ni `F0`.
"""
    path.write_text(text.rstrip() + entry + "\n", encoding="utf-8")


def main() -> None:
    sync_current_state()
    sync_gate_registry()
    sync_status()
    sync_tracker()
    sync_ariane()
    print("F0_GLOBAL_STATE_SYNC_PASS")


if __name__ == "__main__":
    main()
