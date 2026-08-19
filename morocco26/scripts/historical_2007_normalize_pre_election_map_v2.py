#!/usr/bin/env python3
"""Normalize DIRECT pre-election 2007 district/magnitude evidence only.

Inputs are only clean-lineage contemporaneous-source texts recovered before any 2007
outcome ingestion. This normalizer does NOT know or read the official outcome map.
It intentionally accepts false negatives rather than weak joins.
"""
from __future__ import annotations
import hashlib, json, re, subprocess, unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'data'/'goal100'/'historical'/'2007_v2_research'
BASE='2508256551f94ad67c23a39d7263e01202431bfe'
FORBIDDEN=[ROOT/'data'/'goal100'/'historical'/'2007'/'legislative_2007_outcome_canonical.json',ROOT/'data'/'goal100'/'historical'/'2007'/'historical_native_map_outcome_transcription.json']
AR_NUM={'اثنان':2,'اثنين':2,'مقعدين':2,'مقعدان':2,'ثلاثة':3,'الثلاثة':3,'ثلاث':3,'أربعة':4,'اربعة':4,'الأربعة':4,'الاربعة':4,'خمسة':5,'الخمسة':5,'ستة':6,'الستة':6}
NUMTOK=r'(?:\d+|اثنان|اثنين|مقعدين|مقعدان|ثلاثة|الثلاثة|ثلاث|أربعة|اربعة|الأربعة|الاربعة|خمسة|الخمسة|ستة|الستة)'

def guard():
 bad=[str(p.relative_to(ROOT)) for p in FORBIDDEN if p.exists()]
 if bad: raise SystemExit('LEAKAGE_GUARD_FAIL '+repr(bad))
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if subprocess.run(['git','merge-base','--is-ancestor',BASE,head],cwd=ROOT).returncode: raise SystemExit('LEAKAGE_GUARD_FAIL ancestry')
 return {'base':BASE,'head':head,'derived_outcome_paths_present':bad}
def num(t):
 t=t.strip();
 if t.isdigit(): return int(t)
 return AR_NUM.get(t)
def clean_name(s):
 s=re.sub(r'\s+',' ',s).strip(' ،,.;:()[]-–—')
 # trim Arabic relative-clause remnants conservatively
 s=re.split(r'\s+(?:التي|والتي|حيث|فيما|ويتنافس|وتتنافس|يتنافس|تتنافس)\b',s,maxsplit=1)[0].strip()
 return s
def key(s):
 # only for duplicate grouping, never for matching to outcome
 x=unicodedata.normalize('NFKD',s).lower()
 x=re.sub(r'[\s\-–—_()]+','',x)
 x=re.sub(r'[،,.;:\'’"]','',x)
 return x
def load_pages():
 pages=[]
 for fn,lang in [('assahraa_eligible_text_v2.json','ar'),('lematin_eligible_text_v2.json','fr')]:
  p=R/fn
  if not p.exists(): continue
  d=json.loads(p.read_text(encoding='utf-8'))
  for z in d.get('pages',[]): pages.append(z|{'language':lang,'input_file':fn})
 return pages
def add(out,seen,page,name,seats,span,pattern):
 name=clean_name(name)
 if not name or len(name)<2 or len(name)>85 or not seats or not (2<=seats<=6): return
 # reject generic labels; these are not district identities
 low=name.lower()
 generic=('المملكة','العمالة','الإقليم','الاقليم','الجهة','province','préfecture','region','région','chambre','maroc')
 if any(low==g or low.startswith(g+' ') for g in generic): return
 k=(key(name),seats,page['url'])
 if k in seen:return
 seen.add(k)
 text=page['text'];lo=max(0,span[0]-220);hi=min(len(text),span[1]+260)
 out.append({'territory_as_published':name,'magnitude':seats,'publication_date':page['publication_date'],'url':page['url'],'source_sha256':page.get('sha256'),'source_title':page.get('title'),'language':page['language'],'evidence_class':'DIRECT_EXPLICIT_SAME_CONTEXT','parser_pattern':pattern,'supporting_context':text[lo:hi],'status':'VERIFIED_TEXT_RELATION'})
def extract_ar(page,out,seen):
 t=page['text']
 # Normalize parentheses so e.g. دائرة سلا( المدينة becomes one local label.
 tt=t.replace('(',' ').replace(')',' ')
 # district first -> magnitude later in same short clause
 p1=re.compile(r'(?:ب?دائرة|بالدائرة\s+الانتخابية)\s+([^،,.؛]{2,70}?)(?=\s*(?:،|,|التي|والتي|حيث|يتنافس|تتنافس|ويتنافس|وتتنافس))[^.؛]{0,220}?(?:على|للفوز\s*ب|للفوز\s*بال|للفوز\s+بـ?)\s*('+NUMTOK+r')\s*(?:مقاعد|مقعدين|مقعد)',re.I)
 for m in p1.finditer(tt):add(out,seen,page,m.group(1),num(m.group(2)),m.span(),'AR_DISTRICT_THEN_SEATS')
 # magnitude first -> named district later, common MAP wording
 p2=re.compile(r'(?:على|للفوز\s*ب|للفوز\s*بال|للفوز\s+بـ?)\s*('+NUMTOK+r')\s*(?:مقاعد|مقعدين|مقعد)[^.؛،]{0,180}?(?:ب?دائرة|بالدائرة\s+الانتخابية)\s+([^،,.؛]{2,70})',re.I)
 for m in p2.finditer(tt):add(out,seen,page,m.group(2),num(m.group(1)),m.span(),'AR_SEATS_THEN_DISTRICT')
 # Numeric/list formulation: "24 lists ... three seats ... district X" already covered,
 # plus exact named single-district province clauses.
 p3=re.compile(r'(?:الدائرة\s+الانتخابية|دائرة)\s+([^،,.؛]{2,70})[^.؛]{0,180}?('+NUMTOK+r')\s*(?:مقاعد|مقعدين|مقعد)',re.I)
 for m in p3.finditer(tt):add(out,seen,page,m.group(1),num(m.group(2)),m.span(),'AR_GENERIC_DIRECT')
def extract_fr(page,out,seen):
 t=page['text']
 pats=[
  ('FR_DISTRICT_THEN_SEATS',re.compile(r'(?:circonscription(?:\s+électorale)?(?:\s+de|\s+d[\'’])?\s+)([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9\'’\- ]{1,75}?)(?=\s*(?:,|;|:|qui|où|compte|avec))[^.;]{0,220}?(\d+)\s+si[eè]ges?',re.I)),
  ('FR_SEATS_THEN_DISTRICT',re.compile(r'(\d+)\s+si[eè]ges?[^.;]{0,180}?(?:circonscription(?:\s+électorale)?(?:\s+de|\s+d[\'’])?\s+)([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9\'’\- ]{1,75})',re.I)),
 ]
 for label,p in pats:
  for m in p.finditer(t):
   if label=='FR_DISTRICT_THEN_SEATS':name,seats=m.group(1),int(m.group(2))
   else:seats,name=int(m.group(1)),m.group(2)
   add(out,seen,page,name,seats,m.span(),label)
def main():
 lineage=guard(); pages=load_pages(); facts=[];seen=set()
 for p in pages:
  if not p.get('publication_date') or p['publication_date']>'2007-09-06':continue
  (extract_ar if p['language']=='ar' else extract_fr)(p,facts,seen)
 # Group only exact normalized labels. No fuzzy merge, no outcome crosswalk.
 groups={}
 for f in facts:groups.setdefault(key(f['territory_as_published']),[]).append(f)
 promoted=[];conflicts=[]
 for k,fs in groups.items():
  mags=sorted(set(f['magnitude'] for f in fs)); names=sorted(set(f['territory_as_published'] for f in fs))
  row={'normalization_key':k,'published_names':names,'magnitudes':mags,'evidence_count':len(fs),'evidence':fs}
  if len(mags)==1:row|={'magnitude':mags[0],'status':'VERIFIED_DIRECT'};promoted.append(row)
  else:row['status']='AMBIGUOUS_CONFLICT';conflicts.append(row)
 promoted.sort(key=lambda x:x['normalization_key']);conflicts.sort(key=lambda x:x['normalization_key'])
 result={'schema_version':'2.0','research_id':'M26-HIST-2007-DIRECT-MAP-NORMALIZATION-V2','outcome_used':False,'lineage':lineage,'cutoff':'2007-09-06','input_pages':len(pages),'direct_fact_count':len(facts),'unique_verified_label_count':len(promoted),'verified_seat_sum_over_unique_labels':sum(x['magnitude'] for x in promoted),'conflict_count':len(conflicts),'promotion_gate':{'required_unique_districts':95,'required_local_seats':295,'passes_count':len(promoted)==95,'passes_seat_sum':sum(x['magnitude'] for x in promoted)==295,'status':'CANDIDATE_FOR_FREEZE' if len(promoted)==95 and sum(x['magnitude'] for x in promoted)==295 and not conflicts else 'CONTINUE_RECOVERY'},'verified':promoted,'conflicts':conflicts}
 (R/'district_evidence_candidates_v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'pages':len(pages),'facts':len(facts),'unique':len(promoted),'seat_sum':result['verified_seat_sum_over_unique_labels'],'conflicts':len(conflicts),'gate':result['promotion_gate']['status']},ensure_ascii=False))
if __name__=='__main__':main()
