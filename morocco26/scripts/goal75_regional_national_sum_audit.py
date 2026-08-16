#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path
import goal75_p2_exact as p
# NOTE: goal75_p2_exact has main guard and is safe to import.
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75';O.mkdir(exist_ok=True)
# Ministry totals reported by Medias24 for regional-election votes where explicitly published.
EXPECTED={'RNI':2120854}

def main():
    total=Counter();regions=[]
    for name,seats in p.REGIONS:
        from urllib.parse import quote
        slug=p.RSLUG.get(name,'Circonscription_de_'+quote(name.replace(' ','_'),safe="_()'-"));url='https://fr.wikipedia.org/wiki/'+slug
        raw=p.parse_table(p.tabs(url)[-1],'REGION::'+name)
        # keep raw source before any Dakhla correction for national-source transcription audit
        regions.append({'region':name,'votes':raw['votes'],'recognized_sum':raw['recognized_vote_sum'],'registered':raw['registered'],'expressed':raw['expressed'],'url':url})
        for k,v in raw['votes'].items():
            code=p.list_code(k)
            if code: total[code]+=v
    out={'raw_secondary_region_party_sums':dict(sorted(total.items())),'explicit_national_expected':EXPECTED,'RNI_delta_vs_ministry':total['RNI']-EXPECTED['RNI'],'regions':regions}
    (O/'regional_national_sum_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'RNI_secondary_sum':total['RNI'],'RNI_ministry_total':EXPECTED['RNI'],'delta':out['RNI_delta_vs_ministry'],'RNI_by_region':[{r['region']:r['votes'].get('RNI')} for r in regions]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
