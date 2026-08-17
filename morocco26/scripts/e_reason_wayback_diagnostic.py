#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26" / "data" / "goal100" / "e_reason"
RUN_ID = os.environ.get("E_REASON_WAYBACK_RUN_ID") or "wayback_diagnostic_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = ER / "evidence" / "wayback_diagnostics" / RUN_ID
OUT.mkdir(parents=True, exist_ok=False)

TARGETS = [
    (2016, "20161006225959", "https://medias24.com/2016/10/03/legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes/"),
    (2021, "20210907225959", "https://medias24.com/2021/09/05/legislatives-voici-la-liste-des-principaux-candidats-circonscription-par-circonscription/"),
    (2021, "20210907225959", "https://assets.medias24.com/js/carte/election2021/villes/casa/index.html"),
]

session = requests.Session()
session.headers["User-Agent"] = "Atlas395-EReason-WaybackDiagnostic/1.0"
rows = []
for year, cutoff, url in TARGETS:
    endpoint = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": url,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "to": cutoff[:8],
        "limit": "20",
        "collapse": "digest",
    }
    row = {"year": year, "url": url, "cutoff": cutoff, "cdx_ok": False, "snapshots": [], "sample_fetch": None, "error": None}
    try:
        response = session.get(endpoint, params=params, timeout=(5, 12))
        row["cdx_status"] = response.status_code
        row["cdx_bytes"] = len(response.content)
        response.raise_for_status()
        payload = response.json()
        if payload and len(payload) > 1:
            header = payload[0]
            snapshots = [dict(zip(header, x)) for x in payload[1:] if x[0] <= cutoff]
            snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
            row["snapshots"] = snapshots
            row["cdx_ok"] = True
            if snapshots:
                snap = snapshots[0]
                archived = f"https://web.archive.org/web/{snap['timestamp']}id_/{url}"
                try:
                    fetched = session.get(archived, timeout=(5, 15), allow_redirects=True)
                    row["sample_fetch"] = {
                        "url": archived,
                        "status": fetched.status_code,
                        "bytes": len(fetched.content),
                        "sha256": hashlib.sha256(fetched.content).hexdigest() if fetched.content else None,
                        "content_type": fetched.headers.get("content-type"),
                    }
                    if fetched.ok and fetched.content:
                        suffix = ".html" if "html" in (fetched.headers.get("content-type") or "") else ".bin"
                        (OUT / (row["sample_fetch"]["sha256"] + suffix)).write_bytes(fetched.content)
                except Exception as exc:
                    row["sample_fetch"] = {"error": f"{type(exc).__name__}: {exc}"}
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    rows.append(row)

manifest = {
    "schema_version": "1.0",
    "run_id": RUN_ID,
    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "rows": rows,
    "predictive_judgments_generated": False,
    "forecast_delta_generated": False,
    "F1_created": False,
}
(OUT / "diagnostic.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(ER / "wayback_diagnostic_latest.json").write_text(json.dumps({
    "latest_run_id": RUN_ID,
    "latest_manifest": str((OUT / "diagnostic.json").relative_to(ROOT)),
}, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
