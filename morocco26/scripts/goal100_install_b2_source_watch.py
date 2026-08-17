#!/usr/bin/env python3
"""Install append-only official-source monitoring for B2.

The monitor records bytes, HTTP metadata and hashes. It does not extract a
candidate, infer absence, or create forecast-eligible evidence. Interpretation
requires a later deterministic parser or human-structured evidence row.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
B2 = G100 / "b2" / "v1"
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT.parent / ".github" / "workflows"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def monitor_source() -> str:
    return r'''#!/usr/bin/env python3
"""Fetch configured official B2 sources and record append-only acquisition metadata."""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data'/'goal100'/'b2'/'v1'
OUT=B/'source_watch'
registry=json.loads((B/'source_registry.json').read_text(encoding='utf-8'))
now=datetime.now(timezone.utc).replace(microsecond=0)
stamp=now.strftime('%Y%m%dT%H%M%SZ')
path=OUT/f'{stamp}.json'
if path.exists(): raise SystemExit('B2_SOURCE_WATCH_FAIL: append-only timestamp collision')
headers={'User-Agent':'MOROCCO26-B2-SourceWatch/1.0 (+research reproducibility)','Accept':'text/html,application/pdf,application/json,*/*;q=0.8','Accept-Language':'fr,ar;q=0.9,en;q=0.7','Cache-Control':'no-cache'}
session=requests.Session(); session.headers.update(headers)
rows=[]
for source in registry.get('sources',[]):
    url=source.get('url')
    if not url:
        rows.append({'source_id':source.get('source_id'),'url':None,'status':'SKIPPED_NO_EXACT_URL','forecast_evidence_created':False})
        continue
    row={'source_id':source['source_id'],'tier':source.get('tier'),'role':source.get('role'),'url':url,'retrieved_at':now.isoformat(),'forecast_evidence_created':False}
    try:
        response=session.get(url,timeout=45,allow_redirects=True)
        raw=response.content
        row.update({'http_status':response.status_code,'final_url':response.url,'content_type':response.headers.get('content-type'),'etag':response.headers.get('etag'),'last_modified':response.headers.get('last-modified'),'bytes':len(raw),'content_sha256':hashlib.sha256(raw).hexdigest(),'looks_like_html':bool(re.search(br'<(?:!doctype\s+html|html)',raw[:8192],re.I)),'access_state':'OK' if response.status_code==200 else 'WAF_OR_HTTP_ERROR_RECORDED'})
    except Exception as exc:
        row.update({'access_state':'REQUEST_ERROR_RECORDED','error':repr(exc)})
    rows.append(row)
report={'schema_version':'1.0','audit_id':'M26-GOAL100-B2-SOURCE-WATCH-V1','retrieved_at':now.isoformat(),'gate':'PASS_ACQUISITION_METADATA_ONLY','sources':rows,'evidence_rows_created':0,'interpretation_performed':False,'rule':'HTTP failure, 403 or missing exact URL remains explicit and is never translated into political absence.'}
OUT.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'artifact':str(path.relative_to(ROOT.parent)),'sources':len(rows),'http_200':sum(r.get('http_status')==200 for r in rows),'errors':sum(r.get('access_state') in {'WAF_OR_HTTP_ERROR_RECORDED','REQUEST_ERROR_RECORDED'} for r in rows),'evidence_rows_created':0},ensure_ascii=False,indent=2))
'''


def watch_workflow() -> str:
    return '''name: morocco26-b2-source-watch\n\non:\n  workflow_dispatch:\n  push:\n    branches: [morocco26-b2-structured-evidence]\n    paths:\n      - 'morocco26/data/goal100/b2/v1/source_registry.json'\n      - 'morocco26/scripts/goal100_b2_source_watch.py'\n      - '.github/workflows/morocco26-b2-source-watch.yml'\n  schedule:\n    - cron: '17 5 * * *'\n\nconcurrency:\n  group: morocco26-b2-source-watch\n  cancel-in-progress: false\n\npermissions:\n  contents: write\n\njobs:\n  watch:\n    runs-on: ubuntu-latest\n    timeout-minutes: 15\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          ref: morocco26-b2-structured-evidence\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n      - run: pip install --quiet requests\n      - name: Record official-source acquisition metadata\n        run: python morocco26/scripts/goal100_b2_source_watch.py\n      - name: Preserve scientific boundaries\n        run: |\n          python morocco26/scripts/validate_anti_drift.py\n          python morocco26/scripts/goal100_validate_b2_v1.py\n          python - <<'PY'\n          import json\n          from pathlib import Path\n          files=sorted(Path('morocco26/data/goal100/b2/v1/source_watch').glob('*.json'))\n          r=json.loads(files[-1].read_text(encoding='utf-8'))\n          assert r['evidence_rows_created']==0\n          assert r['interpretation_performed'] is False\n          print('B2_SOURCE_WATCH_BOUNDARY_PASS')\n          PY\n      - name: Commit append-only watch artifact\n        run: |\n          git config user.name 'github-actions[bot]'\n          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'\n          git add morocco26/data/goal100/b2/v1/source_watch\n          git commit -m 'data(morocco26): append B2 official-source watch snapshot' || true\n          git pull --rebase origin morocco26-b2-structured-evidence\n          git push origin HEAD:morocco26-b2-structured-evidence\n'''


def main() -> None:
    if not B2.exists():
        raise SystemExit("B2_SOURCE_INSTALL_FAIL: B2 scaffold missing")
    path = B2 / "source_registry.json"
    registry = load(path, {"schema_version": "1.0", "sources": []})
    existing = {row.get("source_id"): row for row in registry.setdefault("sources", [])}
    seeds = [
        {
            "source_id": "MA_SGG_ORGANIC_LAW_27_11",
            "tier": "A_OFFICIAL",
            "role": "electoral law and regional magnitudes",
            "url": "https://www.sgg.gov.ma/Portals/1/textesconsolides/27_11.pdf",
            "status": "ACTIVE"
        },
        {
            "source_id": "MA_PARLIAMENT_ELECTORAL_MAP_AR",
            "tier": "A_OFFICIAL",
            "role": "current local electoral map",
            "url": "https://www.chambredesrepresentants.ma/ar/%D8%AE%D8%B1%D9%8A%D8%B7%D8%A9-%D8%A7%D9%84%D8%AA%D9%82%D8%B3%D9%8A%D9%85-%D8%A7%D9%84%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8%D9%8A",
            "status": "ACTIVE_WITH_WAF_LIMITATION"
        },
        {
            "source_id": "MA_PARLIAMENT_2021_NUMERIC_LIST_FR",
            "tier": "A_OFFICIAL",
            "role": "official constituency names and magnitudes witness",
            "url": "https://www.chambredesrepresentants.ma/fr/actualites/donnees-chiffrees-autour-du-scrutin-legislatif-du-mercredi-8-septembre-2021-conformement",
            "status": "ACTIVE_WITH_WAF_LIMITATION"
        },
        {
            "source_id": "MA_PARLIAMENT_ELECTION_LAWS_AR",
            "tier": "A_OFFICIAL",
            "role": "official election-law index",
            "url": "https://www.chambredesrepresentants.ma/ar/%D8%A7%D9%84%D9%82%D9%88%D8%A7%D9%86%D9%8A%D9%86-%D8%A7%D9%84%D9%85%D8%AA%D8%B9%D9%84%D9%82%D8%A9-%D8%A8%D8%A7%D9%84%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8%D8%A7%D8%AA",
            "status": "ACTIVE_WITH_WAF_LIMITATION"
        },
        {
            "source_id": "MA_INTERIOR_HOME",
            "tier": "A_OFFICIAL",
            "role": "discovery root for election authority publications",
            "url": "https://www.interieur.gov.ma/",
            "status": "DISCOVERY_ROOT_NOT_EVIDENCE_ENDPOINT"
        }
    ]
    for row in seeds:
        existing[row["source_id"]] = row
    registry["sources"] = sorted(existing.values(), key=lambda row: str(row.get("source_id")))
    registry["updated_at"] = NOW
    registry["rule"] = "A discovery root is not itself evidence. Exact publication URLs and content hashes are required for an atomic claim."
    dump(path, registry)

    (SCRIPTS / "goal100_b2_source_watch.py").write_text(monitor_source(), encoding="utf-8")
    (WORKFLOWS / "morocco26-b2-source-watch.yml").parent.mkdir(parents=True, exist_ok=True)
    (WORKFLOWS / "morocco26-b2-source-watch.yml").write_text(watch_workflow(), encoding="utf-8")

    journal_candidates = [ROOT / "FIL_D_ARIANE.md", ROOT / "FIL_ARIANE.md"]
    journal = next((candidate for candidate in journal_candidates if candidate.exists()), journal_candidates[0])
    marker = "B2-A004 — Source watch officiel append-only"
    text = journal.read_text(encoding="utf-8") if journal.exists() else "# MOROCCO//26 — FIL D’ARIANE\n"
    if marker not in text:
        text += f'''\n\n### {NOW} — {marker}\n\n- Cinq endpoints officiels racines/témoins sont configurés pour acquisition hashée.\n- Chaque passage enregistre HTTP, redirection, taille, type, ETag/Last-Modified et SHA-256.\n- Un `403`, WAF ou timeout reste une limite d’accès ; il ne devient jamais une absence politique.\n- Le watch ne crée aucune ligne d’évidence et n’interprète aucun contenu.\n- Les endpoints exacts des partis restent des tâches de discovery, non des domaines devinés.\n- Prochaine action exacte : exécuter le watch, résoudre les endpoints d’autorité électorale et de partis, puis convertir seulement les publications admissibles en lignes atomiques validées.\n'''
        journal.write_text(text, encoding="utf-8")

    dump(B2 / "source_watch_installation_status.json", {
        "schema_version": "1.0",
        "installation_id": "M26-GOAL100-B2-SOURCE-WATCH-INSTALL-V1",
        "created_at": NOW,
        "status": "PASS_INSTALLED",
        "configured_exact_urls": len(seeds),
        "evidence_rows_created": 0,
        "interpretation_performed": False,
        "workflow": ".github/workflows/morocco26-b2-source-watch.yml",
        "next_action": "Execute source watch and resolve exact candidate/list publication endpoints."
    })
    print((B2 / "source_watch_installation_status.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
