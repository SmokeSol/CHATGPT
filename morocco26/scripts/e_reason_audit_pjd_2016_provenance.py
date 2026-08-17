#!/usr/bin/env python3
"""Audit whether migrated official PJD 2016 PDFs preserve pre-election documents.

This script does not itself promote evidence. It freezes mechanical provenance
facts needed for a later admissibility decision: official article publication
metadata, attachment linkage, PDF metadata/trailer IDs, page/text fingerprints,
and pre/post-election lexical checks.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
LATEST=ER/'pjd_2016_documents_latest.json'
OUT=ER/'evidence/pjd_2016_provenance_audit'
CUTOFF='2016-10-06T22:59:59+00:00'

PRE_PHRASES=[
    'اقتراع يوم 7 أكتوبر',
    'لائحة المرشحين',
    'مرشحي اللائحة',
    'تمت تزكيتها',
    'الأمانة العامة',
]
POST_TERMS=['نتائج اقتراع','النتائج النهائية','فاز بالمقعد','المقاعد المحصل عليها','حصل على مقعد','الفائزون']


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_pdf_date(value):
    if not value:
        return None
    s=str(value).strip()
    m=re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?",s)
    if not m:
        return None
    y=int(m.group(1)); mo=int(m.group(2) or 1); d=int(m.group(3) or 1)
    hh=int(m.group(4) or 0); mm=int(m.group(5) or 0); ss=int(m.group(6) or 0)
    try:
        return datetime(y,mo,d,hh,mm,ss,tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def html_dates(text: str):
    vals=set()
    for pat in [
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',
        r'content=["\']([^"\']+)["\'][^>]*property=["\']article:published_time["\']',
    ]:
        vals.update(m.group(1) for m in re.finditer(pat,text,re.I))
    return sorted(vals)


def pdf_hrefs(text: str, base_expected: str):
    soup=BeautifulSoup(text,'html.parser')
    rows=[]
    expected_stem=Path(base_expected).stem.casefold()
    for a in soup.find_all('a'):
        href=str(a.get('href') or '')
        if '.pdf' not in href.casefold():
            continue
        basename=Path(urlparse(href).path).name
        stem=Path(basename).stem.casefold()
        rows.append({
            'href':href,
            'basename':basename,
            'expected_exact_basename':basename.casefold()==base_expected.casefold(),
            'expected_migration_variant':stem in {expected_stem,expected_stem+'_0'},
        })
    return rows


def trailer_id(reader: PdfReader):
    try:
        ids=reader.trailer.get('/ID')
        if not ids:
            return None
        return [bytes(x).hex() if hasattr(x,'__bytes__') else str(x) for x in ids]
    except Exception:
        return None


def main():
    latest=json.loads(LATEST.read_text(encoding='utf-8'))
    manifest_path=ROOT/latest['latest_manifest']
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    docs={x['article_id']:x for x in manifest['documents'] if x.get('transport')=='CURRENT_STATIC_MIRROR_DISCOVERY_ONLY'}
    rows=[]
    for article in manifest['articles']:
        aid=article['id']; doc=docs.get(aid)
        if not doc:
            continue
        html_path=ROOT/article['current_page']['path']
        pdf_path=ROOT/doc['raw_path']
        text_path=ROOT/doc['text_path']
        htext=html_path.read_text(encoding='utf-8',errors='replace')
        ptext=text_path.read_text(encoding='utf-8',errors='replace')
        reader=PdfReader(str(pdf_path))
        metadata={str(k):str(v) for k,v in (reader.metadata or {}).items()}
        creation=parse_pdf_date(metadata.get('/CreationDate'))
        modification=parse_pdf_date(metadata.get('/ModDate'))
        dates=html_dates(htext)
        hrefs=pdf_hrefs(htext,article['expected_attachment'])
        expected_stem=Path(article['expected_attachment']).stem.casefold()
        linked=[x for x in hrefs if x['expected_exact_basename'] or x['expected_migration_variant']]
        page_hashes=[]
        extracted=[]
        for page in reader.pages:
            t=page.extract_text() or ''
            extracted.append(t)
            page_hashes.append(hashlib.sha256(t.encode('utf-8')).hexdigest())
        combined='\n'.join(extracted)
        phrase_hits={p:(p in combined or p in ptext) for p in PRE_PHRASES}
        post_hits={p:(p in combined or p in ptext) for p in POST_TERMS}
        publication_pre_cutoff=False
        for value in dates:
            try:
                dt=datetime.fromisoformat(value.replace('Z','+00:00'))
                if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                if dt.astimezone(timezone.utc)<=datetime.fromisoformat(CUTOFF): publication_pre_cutoff=True
            except Exception:
                pass
        metadata_pre_cutoff=None
        if creation:
            metadata_pre_cutoff=datetime.fromisoformat(creation)<=datetime.fromisoformat(CUTOFF)
        mechanical_pass=(
            publication_pre_cutoff
            and bool(linked)
            and phrase_hits['اقتراع يوم 7 أكتوبر']
            and phrase_hits['لائحة المرشحين']
            and not any(post_hits.values())
        )
        rows.append({
            'article_id':aid,
            'official_article_url':article['url'],
            'article_published_at_declared':article['published_at_source'],
            'html_detected_publication_dates':dates,
            'publication_pre_cutoff':publication_pre_cutoff,
            'expected_attachment':article['expected_attachment'],
            'pdf_links_on_current_official_article':hrefs,
            'expected_attachment_linked':bool(linked),
            'mirror_url':doc['url'],
            'mirror_basename':Path(urlparse(doc['url']).path).name,
            'pdf_sha256':sha256(pdf_path),
            'pdf_bytes':pdf_path.stat().st_size,
            'page_count':len(reader.pages),
            'pdf_metadata':metadata,
            'pdf_creation_date_parsed_utc_assumption':creation,
            'pdf_modification_date_parsed_utc_assumption':modification,
            'pdf_creation_pre_cutoff_if_present':metadata_pre_cutoff,
            'pdf_trailer_id':trailer_id(reader),
            'extracted_text_sha256':hashlib.sha256(combined.encode('utf-8')).hexdigest(),
            'page_text_sha256':page_hashes,
            'pre_election_phrase_hits':phrase_hits,
            'post_election_outcome_term_hits':post_hits,
            'mechanical_provenance_checks_pass':mechanical_pass,
            'admissibility_promoted_by_this_audit':False,
        })
    payload={
        'schema_version':'1.0',
        'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source_manifest':str(manifest_path.relative_to(ROOT)),
        'purpose':'PROVENANCE_AUDIT_ONLY_NO_AUTOMATIC_PROMOTION',
        'documents_audited':len(rows),
        'mechanical_pass_count':sum(r['mechanical_provenance_checks_pass'] for r in rows),
        'all_mechanical_checks_pass':bool(rows) and all(r['mechanical_provenance_checks_pass'] for r in rows),
        'rows':rows,
        'invariants':{
            'predictive_judgments_generated':False,
            'forecast_delta_generated':False,
            'outcomes_unsealed':False,
            'F1_created':False,
        },
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'audit.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({
        'documents_audited':payload['documents_audited'],
        'mechanical_pass_count':payload['mechanical_pass_count'],
        'all_mechanical_checks_pass':payload['all_mechanical_checks_pass'],
        'rows':[{
            'article_id':r['article_id'],
            'published_dates':r['html_detected_publication_dates'],
            'attachment_linked':r['expected_attachment_linked'],
            'creation':r['pdf_creation_date_parsed_utc_assumption'],
            'creation_pre_cutoff':r['pdf_creation_pre_cutoff_if_present'],
            'page_count':r['page_count'],
            'mechanical_pass':r['mechanical_provenance_checks_pass'],
        } for r in rows]
    },ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
