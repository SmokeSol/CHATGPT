#!/usr/bin/env python3
import csv,json,math,re
from collections import Counter
from io import StringIO
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import goal75_stage1 as g
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75';O.mkdir(exist_ok=True)
OFFICIAL_TOTAL={'RNI':102,'PAM':87,'PI':81,'USFP':34,'MP':28,'PPS':22,'UC':18,'PJD':13,'MDS':5,'FFD':3,'CNI':1,'PSU':1}
OFFICIAL_CODES=set(OFFICIAL_TOTAL)
REGIONS=[('Rabat-Salé-Kénitra',10),('Laâyoune-Sakia El Hamra',5),('Dakhla-Oued Eddahab',3),('Drâa-Tafilalet',6),('Casablanca-Settat',12),('Souss-Massa',7),('Guelmim-Oued Noun',5),('Marrakech-Safi',10),('Tanger-Tétouan-Al Hoceïma',8),('Oriental',7),('Fès-Meknès',10),('Béni Mellal-Khénifra',7)]
RSLUG={'Dakhla-Oued Eddahab':'Circonscription_de_Dakhla-Oued_Ed-Dahab','Oriental':"Circonscription_d%27Oriental"}
OV={('beni-mellal',2021,'registered'):318608}

def list_key(label):
    """Return a collision-safe electoral-list identity.

    Codes are canonical only for parties that actually won House seats in 2021.
    All other lists retain a normalized full-name identity so acronym collisions
    (e.g. two distinct PE lists in Sidi Bernoussi) cannot merge votes.
    """
    label=str(label).strip()
    if not label or label.lower() in ('nan','none'):
        return None
    code=g.party(label)
    if code in OFFICIAL_CODES:
        return code
    full=g.norm(re.sub(r'\([A-Z][A-Z0-9-]{1,7}\)\s*$', '', label))
    if not full or full in ('nan','none'):
        return None
    return f'LIST::{code or "NA"}::{full}'

def display_key(k):
    return k if not str(k).startswith('LIST::') else k

def parse_table(df,cid=None):
    df=g.flatcols(df)
    pc=next((c for c in df.columns if 'Parti' in str(c)),None)
    vcs=[c for c in df.columns if 'Voix' in str(c) and '%' not in str(c)] or [c for c in df.columns if 'Voix' in str(c)]
    if pc is None or not vcs:raise RuntimeError(f'party/vote columns missing {cid}: {list(df.columns)}')
    vc=vcs[0]
    ec=next((c for c in df.columns if 'élu' in str(c).lower() or 'elu' in g.norm(c)),None)
    votes={};reg=exp=None;elected=Counter();labels={}
    for _,r in df.iterrows():
        label=str(r[pc]).strip();text=' | '.join(str(v) for v in r.tolist());nt=g.norm(text);v=g.nint(r[vc])
        if 'inscrits' in nt:reg=v;continue
        if 'exprimes' in nt:exp=v;continue
        k=list_key(label)
        if not k or v is None:continue
        labels.setdefault(k,label)
        # rowspan can repeat an identical list/vote pair for each elected candidate.
        if k not in votes:votes[k]=v
        elif votes[k]!=v:raise RuntimeError(f'conflicting duplicated vote rows {cid} {k}: {votes[k]} vs {v}; labels={labels[k]!r}/{label!r}')
        if ec is not None:
            z=str(r[ec]).strip().lower()
            if z not in ('','nan','none','-','—'):elected[k]+=1
    if cid=='beni-mellal':reg=OV[(cid,2021,'registered')]
    if exp is None or (cid=='beni-mellal' and exp<sum(votes.values())):exp=sum(votes.values())
    return {'votes':votes,'registered':reg,'expressed':exp,'elected_party_counts':dict(elected),'recognized_vote_sum':sum(votes.values()),'labels':labels}

def tabs(url):
    html=g.get(url).text
    return [x for x in pd.read_html(StringIO(html)) if 'Parti' in ' '.join(map(str,x.columns)) and 'Voix' in ' '.join(map(str,x.columns))]

def alloc(v,seats,reg):
    q=reg/seats;base={p:math.floor(n/q) for p,n in v.items()};a=base.copy();left=seats-sum(base.values())
    if left<0:raise RuntimeError(f'mathematical violation direct seats {sum(base.values())}>{seats}')
    rem={p:v[p]-base[p]*q for p in v}
    for p in sorted(v,key=lambda p:(-rem[p],-v[p],p)):
        if left<=0:break
        a[p]=a.get(p,0)+1;left-=1
    return {p:n for p,n in a.items() if n}

def exact(a,b):return {k:v for k,v in a.items() if v}=={k:v for k,v in b.items() if v}

def official_only(d):return {k:v for k,v in d.items() if k in OFFICIAL_CODES and v}

def main():
    cfg=list(csv.DictReader(open(D/'constituencies_goal75.csv',encoding='utf-8')));local=[];lm=[]
    for i,x in enumerate(cfg,1):
        name=x['name'];seats=int(x['seats']);_,url=g.resolve(name);t=tabs(url)[-1];p=parse_table(t,x['constituency_id']);assert p['registered'] and p['recognized_vote_sum']<=p['registered'];a=alloc(p['votes'],seats,p['registered'])
        # 2021 local empirical property: every elected list got one local seat.
        elected={k:1 for k,v in p['elected_party_counts'].items() if v>0};rank=set(sorted(p['votes'],key=p['votes'].get,reverse=True)[:seats]);legal_set=set(a)
        empirical_ok=(not elected or elected=={k:1 for k in legal_set}) and len(legal_set)==seats and legal_set==rank
        if not empirical_ok:raise RuntimeError(f'local elected mismatch {name}: legal={a} elected={elected} rank={rank}')
        rr=sorted(p['votes'].items(),key=lambda z:(-z[1],z[0]));cut1,cut2=rr[seats-1],rr[seats]
        lm.append({'constituency_id':x['constituency_id'],'name':name,'region':x['region'],'seats':seats,'registered':p['registered'],'expressed':p['expressed'],'legal_winners':a,'last_rank_party':cut1[0],'last_rank_votes':cut1[1],'first_nonwinner':cut2[0],'first_nonwinner_votes':cut2[1],'raw_margin_votes':cut1[1]-cut2[1],'source_url':url})
        local.append({'constituency_id':x['constituency_id'],'name':name,'region':x['region'],'seats':seats,'registered':p['registered'],'expressed':p['expressed'],'legal_replay':a,'elected_party_counts':elected,'source_url':url});print('L',i,name,a,flush=True)
    reg=[]
    for i,(name,seats) in enumerate(REGIONS,1):
        slug=RSLUG.get(name,'Circonscription_de_'+quote(name.replace(' ','_'),safe="_()'-"));url='https://fr.wikipedia.org/wiki/'+slug;t=tabs(url)[-1];p=parse_table(t,'REGION::'+name);assert p['registered'] and p['recognized_vote_sum']<=p['registered'];a=alloc(p['votes'],seats,p['registered']);e=p['elected_party_counts']
        if sum(e.values())!=seats or not exact(a,e):raise RuntimeError(f'regional elected mismatch {name}: legal={a} elected={e}')
        reg.append({'region':name,'seats':seats,'registered':p['registered'],'expressed':p['expressed'],'legal_replay':a,'elected_party_counts':e,'source_url':url});print('R',i,name,a,flush=True)
    def agg(rows):
        c=Counter()
        for z in rows:c.update(official_only(z['legal_replay']))
        return dict(sorted(c.items()))
    la,ra=agg(local),agg(reg);total=Counter(la);total.update(ra);total=dict(sorted(total.items()))
    out={'method':'LO_04_21_article_84_registered_voters_divided_by_seats_then_largest_remainders','identity_rule':'official seat-winning codes canonical; all other electoral lists keyed by normalized full name to prevent acronym collisions','local':{'constituencies':len(local),'seats':sum(sum(z['legal_replay'].values()) for z in local),'aggregate':la,'every_constituency_empirically_reproduced':True},'regional':{'constituencies':len(reg),'seats':sum(sum(z['legal_replay'].values()) for z in reg),'aggregate':ra,'every_region_empirically_reproduced':True},'total':{'seats':sum(sum(z['legal_replay'].values()) for z in local)+sum(sum(z['legal_replay'].values()) for z in reg),'aggregate':total,'official_expected':OFFICIAL_TOTAL,'exact_official_match':exact(total,OFFICIAL_TOTAL)},'beni_mellal_override':{'registered':318608,'reason':'secondary page turnout block internally impossible; override documented in source_overrides_goal75.json'},'forecast_status':'BLOCKED'}
    (O/'local_2021_replay_exact.json').write_text(json.dumps(local,ensure_ascii=False,indent=2));(O/'regional_2021_replay_exact.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2));(O/'seat_margin_92.json').write_text(json.dumps(lm,ensure_ascii=False,indent=2));(O/'p2_exact_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(0 if out['local']['seats']==305 and out['regional']['seats']==90 and out['total']['exact_official_match'] else 9)
main()
