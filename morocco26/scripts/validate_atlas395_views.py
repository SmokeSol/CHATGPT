#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
M26=Path(__file__).resolve().parents[1]
DEFAULT_DATA=M26/'web'/'data';DEFAULT_EDITIONS=M26/'web'/'editions'
def load(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def require(cond,msg):
    if not cond: raise SystemExit(f'ATLAS395_VALIDATION_FAIL: {msg}')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',type=Path,default=DEFAULT_DATA);ap.add_argument('--editions-dir',type=Path,default=DEFAULT_EDITIONS);ap.add_argument('--require-daily',action='store_true');args=ap.parse_args();data=args.data_dir
    snap=load(data/'current_snapshot.json');nat=load(data/'national_projection.json');cards=load(data/'constituency_cards.json');parties=load(data/'party_cards.json');meth=load(data/'methodology_state.json');man=load(data/'snapshot_manifest.json')
    require(snap.get('status')=='FROZEN','displayed forecast snapshot must be frozen');require(snap.get('read_only_contract') is True,'read-only product contract missing')
    g=snap.get('geometry') or {};require(g.get('local_constituencies')==92,'local constituency count != 92');require(g.get('local_seats')==305,'local seats != 305');require(g.get('regional_constituencies')==12,'regional constituency count != 12');require(g.get('regional_seats')==90,'regional seats != 90');require(g.get('total_seats')==395,'total seats != 395')
    require(nat.get('total_seats')==395 and nat.get('local_seats')==305 and nat.get('regional_seats')==90,'national seat accounting mismatch');require(cards.get('count')==92 and len(cards.get('constituencies') or [])==92,'constituency cards != 92');require(sum(int(c.get('magnitude') or 0) for c in cards['constituencies'])==305,'local magnitude sum != 305');require(len(parties.get('parties') or [])==9,'party buckets != 9')
    sep=meth.get('scientific_separation') or {};require(sep.get('atlas_views_are_model_inputs') is False,'Atlas views cannot become model inputs');require(sep.get('atlas_writes_scientific_artifacts') is False,'Atlas cannot write scientific artifacts');require(sep.get('unknown_preserved') is True,'missing information must remain explicitly missing')
    generated=man.get('generated_from') or {};require(generated.get('snapshot_id')==snap.get('snapshot_id'),'public manifest/current snapshot mismatch');require(generated.get('forecast_sha256')==snap.get('forecast_sha256'),'forecast hash mismatch across public views')
    for name,expected in (man.get('outputs') or {}).items(): require((data/name).exists() and sha(data/name)==expected,f'public output hash mismatch {name}')
    for c in cards['constituencies']:
        for p in (c.get('parties') or {}).values():
            for key in ('p_ge_1','p_ge_2'):
                v=p.get(key)
                if v is not None: require(-1e-12<=float(v)<=1+1e-12,f'invalid probability {key}')
            pk=p.get('p_seats_k') or []
            if pk: require(abs(sum(float(x) for x in pk)-1.0)<1e-6,'seat distribution does not sum to 1')
    if args.require_daily:
        daily=load(data/'daily_update.json');current=load(args.editions_dir/'current.json');index=load(args.editions_dir/'index.json');eid=current.get('edition_id');require(bool(eid),'daily current pointer has no edition id');require(index.get('current_edition')==eid,'daily pointers disagree');edir=args.editions_dir/str(eid);em=load(edir/'edition.json');require(em.get('forecast_snapshot')==snap.get('snapshot_id'),'edition/forecast mismatch');require(em.get('product_version')==current.get('product_version'),'edition/product version mismatch');require(isinstance(daily.get('projection_changed'),bool),'daily projection_changed must be boolean')
        for name,expected in (em.get('files') or {}).items(): require((edir/name).exists() and sha(edir/name)==expected,f'immutable edition hash mismatch {name}')
    print(f"ATLAS395_VALIDATION_OK snapshot={snap.get('snapshot_id')} constituencies=92 seats=395 daily={args.require_daily} read_only=true")
if __name__=='__main__': main()
