#!/usr/bin/env bash
set -euo pipefail

ROOT="morocco26"
G100="$ROOT/data/goal100"

python - <<'PY'
from pathlib import Path

# Correct implementation-only defects before evidentiary execution.
p=Path('morocco26/scripts/goal100_fit_local_N_posterior.py')
s=p.read_text(encoding='utf-8')
locus='    def audit_contest(row: dict, n_values: np.ndarray, label: str, identifier: str) -> dict:\n        turnout = float(row["turnout_rate_reported"])'
replacement='    def audit_contest(row: dict, n_values: np.ndarray, label: str, identifier: str) -> dict:\n        nonlocal scale_tests\n        turnout = float(row["turnout_rate_reported"])'
if locus in s:
    s=s.replace(locus,replacement,1)
elif '        nonlocal scale_tests\n        turnout = float(row["turnout_rate_reported"])' not in s:
    raise SystemExit('N92 correction locus absent')
p.write_text(s,encoding='utf-8')

p=Path('morocco26/scripts/goal100_run_fminus1.py')
s=p.read_text(encoding='utf-8')
locus='    correlation = np.corrcoef(national_seats.astype(float), rowvar=False)\n'
replacement='    correlation = np.corrcoef(national_seats.astype(float), rowvar=False)\n    correlation = np.nan_to_num(correlation, nan=0.0, posinf=0.0, neginf=0.0)\n    np.fill_diagonal(correlation, 1.0)\n'
if locus in s and 'np.nan_to_num(correlation' not in s:
    s=s.replace(locus,replacement,1)
elif 'np.nan_to_num(correlation' not in s:
    raise SystemExit('correlation correction locus absent')
s=s.replace('fminus1_protocol_v1.json','fminus1_protocol_v1_1.json')
p.write_text(s,encoding='utf-8')

p=Path('morocco26/scripts/goal100_finalize_fminus1_manifest.py')
s=p.read_text(encoding='utf-8').replace('fminus1_protocol_v1.json','fminus1_protocol_v1_1.json')
p.write_text(s,encoding='utf-8')

Path('morocco26/scripts/validate_goal100_tracking.py').write_text(
    '#!/usr/bin/env python3\n'
    '"""Stable entry point for the evidence-driven Goal100 validator."""\n'
    'from validate_goal100_tracking_dynamic import main\n\n'
    'if __name__ == "__main__":\n'
    '    main()\n', encoding='utf-8')

journal=Path('morocco26/FIL_ARIANE.md')
text=journal.read_text(encoding='utf-8')
if 'Amendment pré-exécution du cutoff' not in text:
    entry_id='A004' if 'Entrée A004 —' not in text else 'A014'
    text += f'''\n\n### 2026-08-16 — Entrée {entry_id} — Amendment pré-exécution du cutoff\n\n**Constat :** `fminus1_protocol_v1.json` utilisait une borne de fin de journée potentiellement postérieure à l’heure réelle d’émission.\n\n**Correction :** `data/goal100/fminus1_protocol_v1_1.json`, cutoff `2026-08-16T20:00:00+01:00`.\n\n**Timing :** avant toute exécution F−1 et sans observation d’un output de forecast.\n\n**Impact :** aucun paramètre, seuil ou seed modifié ; provenance uniquement. V1 est conservé.\n'''
    journal.write_text(text,encoding='utf-8')
PY

python -m py_compile \
  "$ROOT/scripts/goal100_probe_official_geometry.py" \
  "$ROOT/scripts/goal100_certify_geometry_2026.py" \
  "$ROOT/scripts/goal100_fit_local_N_posterior.py" \
  "$ROOT/scripts/goal100_calibrate_uncertainty.py" \
  "$ROOT/scripts/goal100_run_fminus1.py" \
  "$ROOT/scripts/goal100_reconcile_fminus1_state.py" \
  "$ROOT/scripts/goal100_finalize_fminus1_manifest.py" \
  "$ROOT/scripts/goal100_register_fminus1.py" \
  "$ROOT/scripts/goal100_sync_fil_ariane.py" \
  "$ROOT/scripts/validate_goal100_tracking_dynamic.py" \
  "$ROOT/scripts/validate_goal100_tracking.py"

python "$ROOT/scripts/goal100_probe_official_geometry.py"
python "$ROOT/scripts/goal100_certify_geometry_2026.py"
python "$ROOT/scripts/goal100_fit_local_N_posterior.py"
python "$ROOT/scripts/goal100_calibrate_uncertainty.py"
python "$ROOT/scripts/goal100_reconcile_fminus1_state.py"
python "$ROOT/scripts/goal100_sync_fil_ariane.py"
python "$ROOT/scripts/validate_anti_drift.py"
python "$ROOT/scripts/validate_goal100_tracking_dynamic.py"

# Refresh official legal evidence at the exact simulation execution.
python "$ROOT/scripts/goal100_probe_official_geometry.py"
python "$ROOT/scripts/goal100_certify_geometry_2026.py"
python "$ROOT/scripts/goal100_run_fminus1.py"

python - <<'PY'
import json
from pathlib import Path
g=Path('morocco26/data/goal100')
s=json.loads((g/'simulation_certificate.json').read_text(encoding='utf-8'))
m=json.loads((g/'snapshots/F-1/manifest.json').read_text(encoding='utf-8'))
f=json.loads((g/'snapshots/F-1/forecast.json').read_text(encoding='utf-8'))
assert s['gate']=='PASS' and s['valid_election_draws']>=50000
event={
    'event_id':'A011','date':'2026-08-16','title':'Simulation F-1 cohérente terminée',
    'gate':'MC-50000-COHERENT','status':'PASS',
    'machine_result':{
        'valid_draws':s['valid_election_draws'],'attempts':s['attempted_joint_draws'],
        'rejection_rate':s['legal_rejection_rate'],
        'max_probability_normalization_error':s['max_probability_normalization_error'],
        'monte_carlo_max_binomial_se':s['monte_carlo_max_binomial_standard_error'],
        'OTHER_single_list_calls':s['OTHER_single_list_allocator_calls'],
        'manifest_sha256':m['manifest_sha256'],'forecast_sha256':m['forecast_artifact_hash'],
        'expected_national_seats':{p:round(v['total_seats']['mean'],4) for p,v in f['national_395']['parties'].items()}
    },
    'decision':'Simulation gate eligible for closure; registry insertion remains separate.',
    'next_action':'Reconcile, bind evidence commit, register F-1.'
}
d=g/'fil_ariane_events'; d.mkdir(parents=True,exist_ok=True)
(d/'A011.json').write_text(json.dumps(event,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
PY

python "$ROOT/scripts/goal100_reconcile_fminus1_state.py"
python "$ROOT/scripts/goal100_sync_fil_ariane.py"
python "$ROOT/scripts/validate_anti_drift.py"
python "$ROOT/scripts/validate_goal100_tracking_dynamic.py"

git config user.name 'github-actions[bot]'
git config user.email '41898282+SmokeSol@users.noreply.github.com'
git add morocco26
git commit -m 'evidence(morocco26): execute calibrated 50k-election F-1 model'
EVIDENCE_COMMIT=$(git rev-parse HEAD)
echo "F-1 evidence commit: $EVIDENCE_COMMIT"

python "$ROOT/scripts/goal100_finalize_fminus1_manifest.py"
python "$ROOT/scripts/goal100_register_fminus1.py"
python "$ROOT/scripts/goal100_sync_fil_ariane.py"
python "$ROOT/scripts/validate_anti_drift.py"
python "$ROOT/scripts/validate_goal100_tracking_dynamic.py"

python - <<'PY'
import json
from pathlib import Path
g=Path('morocco26/data/goal100')
reg=json.loads((g/'forecast_registry.json').read_text(encoding='utf-8'))
cert=json.loads((g/'fminus1_registration_certificate.json').read_text(encoding='utf-8'))
state=json.loads((g/'current_state.json').read_text(encoding='utf-8'))
gates=json.loads((g/'gate_registry.json').read_text(encoding='utf-8'))
assert cert['gate']=='PASS'
assert [x['snapshot_id'] for x in reg['snapshots']]==['F-1']
assert reg['sequence']['next_id']=='F0'
assert state['goal100_objective']['forecast_status']=='F-1_ISSUED_IMMUTABLE'
assert all(x['status']=='CLOSED' for x in gates['forecast_unlock'])
assert all(x['status']=='LOCKED' for x in gates['agentic_unlock'])
print(json.dumps({
  'snapshot':'F-1','forecast_sha256':cert['forecast_artifact_sha256'],
  'manifest_sha256':cert['manifest_sha256'],'next':'F0',
  'p0':{x['id']:x['status'] for x in gates['p0']}
},indent=2))
PY

git add morocco26
git commit -m 'milestone(morocco26): register immutable probabilistic forecast F-1'
