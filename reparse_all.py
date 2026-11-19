import fitz, re, sys, time, httpx, os, json, collections
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')

from app.services import pdf_extraction
from app.services.parser import parse_pdf_with_vision, extract_answer_key

API = 'http://13.233.27.70/api/v1'
PAPERS_DIR = r'C:\Users\himan\Desktop\pdf2test\previous papers'
REPORT = r'C:\Users\himan\Desktop\pdf2test\reparse_all_report.json'

BRANCH_MAP = {'AI': 'DA', 'CE': 'CE', 'CSE': 'CS', 'ECE': 'EC', 'EE': 'EE', 'ME': 'ME'}
BRANCH_NAMES = {
    'CS': 'Computer Science and Information Technology',
    'EC': 'Electronics and Communication Engineering',
    'EE': 'Electrical Engineering',
    'ME': 'Mechanical Engineering',
    'CE': 'Civil Engineering',
    'DA': 'Data Science and Artificial Intelligence',
}

r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}
exams = httpx.get(f'{API}/me/exams', headers=h, timeout=30).json()
by_title = collections.defaultdict(list)
for e in exams:
    by_title[e['title']].append(e)


def parse_filename(filename):
    name = filename.replace('.pdf', '')
    m = re.match(r'GATE\s+(\w+)\s+(\d{4})(?:\s+Set\s+(\d+))?\s+Question Paper', name, re.I)
    if not m:
        return None
    branch_str = m.group(1).upper()
    year = int(m.group(2))
    set_num = int(m.group(3)) if m.group(3) else 1
    branch_code = BRANCH_MAP.get(branch_str)
    if not branch_code:
        return None
    return branch_code, year, set_num


def title_for(branch, year, set_num):
    set_str = f' Set {set_num}' if set_num > 1 else ''
    t = f'GATE {year}{set_str} - {BRANCH_NAMES[branch]}'
    if t not in by_title:
        t1 = f'GATE {year} Set 1 - {BRANCH_NAMES[branch]}'
        if t1 in by_title:
            return t1
    return t


def parse_pdf_local(pdf_path):
    ext = pdf_extraction.extract_text(pdf_path, ocr_enabled=False)
    full_text = pdf_extraction.extraction_to_text(ext)
    ak = extract_answer_key(full_text)

    doc = fitz.open(pdf_path)
    total = doc.page_count
    ak_page = None
    for i in range(total):
        pt = doc[i].get_text()
        if 'Answer Key' in pt and re.search(r'^\s*1\.\s*[A-D]', pt, re.M):
            ak_page = i
            break
    question_end = ak_page if ak_page is not None else total
    doc.close()

    all_q = []
    for start in range(0, question_end, 5):
        end = min(start + 5, question_end)
        new_doc = fitz.open()
        src = fitz.open(pdf_path)
        for i in range(start, end):
            new_doc.insert_pdf(src, from_page=i, to_page=i)
        src.close()
        chunk = r'C:\Users\himan\Desktop\pdf2test\_batch_chunk.pdf'
        new_doc.save(chunk)
        new_doc.close()

        ok = False
        for attempt in range(3):
            try:
                res = parse_pdf_with_vision(chunk)
                all_q.extend(res.questions)
                print(f'    pages {start+1}-{end}: {len(res.questions)} Qs', flush=True)
                ok = True
                break
            except Exception as e:
                print(f'    pages {start+1}-{end} attempt {attempt+1} failed: {str(e)[:90]}', flush=True)
                time.sleep(6)
        if not ok:
            print(f'    pages {start+1}-{end}: FAILED', flush=True)

    for i, q in enumerate(all_q):
        n = i + 1
        q.prompt = re.sub(r'^\.?\s*MCQ\s*\([^)]*\)\s*', '', q.prompt).strip()
        q.prompt = re.sub(r'^\.?\s*NAT\s*', '', q.prompt).strip()
        if n not in ak:
            continue
        ans = ak[n].strip()
        m = re.match(r'^([\d.]+)\s+to\s+([\d.]+)$', ans)
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            q.answer_key = round((lo + hi) / 2, 6)
            q.tolerance = round((hi - lo) / 2, 6)
            q.qtype = 'numeric'
        elif ',' in ans and not ans.replace(',', '').replace(' ', '').isdigit():
            q.answer_key = [a.strip() for a in ans.split(',') if a.strip()]
            q.qtype = 'multiple_select'
        elif re.fullmatch(r'[A-D]', ans):
            q.answer_key = ans
            if q.qtype not in ('multiple_select', 'numeric'):
                q.qtype = 'single_choice'
        else:
            clean = ans.strip('()').strip()
            try:
                q.answer_key = float(clean)
                q.qtype = 'numeric'
                q.tolerance = 0.01 if '.' in clean else 0.0
            except ValueError:
                q.answer_key = clean
    return all_q


def to_authoring(q, idx):
    opts = []
    for o in (q.options or []):
        if isinstance(o, dict):
            opts.append({'id': o.get('id', ''), 'text': o.get('text', '')})
        else:
            opts.append({'id': getattr(o, 'id', ''), 'text': getattr(o, 'text', '')})
    return {
        'order_index': idx,
        'qtype': q.qtype,
        'prompt': q.prompt,
        'options': opts,
        'answer_key': q.answer_key,
        'explanation': q.explanation,
        'points': q.points if q.points is not None else 4.0,
        'negative_points': q.negative_points if q.negative_points is not None else -1.0,
        'tolerance': q.tolerance,
        'topic_tags': q.topic_tags or [],
        'section': q.section,
        'source_page': q.source_page,
        'parse_confidence': 0.8,
        'review_status': 'needs_review',
    }


pdfs = sorted(f for f in os.listdir(PAPERS_DIR) if f.lower().endswith('.pdf'))
report = []

for idx, fname in enumerate(pdfs):
    info = parse_filename(fname)
    if not info:
        continue
    branch, year, set_num = info
    title = title_for(branch, year, set_num)
    es = by_title.get(title, [])
    if len(es) != 1:
        print(f'[{idx+1}/{len(pdfs)}] SKIP (no unique exam): {title}', flush=True)
        continue
    exam = es[0]

    # Skip DA (already fixed)
    if branch == 'DA':
        continue

    ex = httpx.get(f"{API}/exams/{exam['id']}", headers=h, timeout=60).json()
    qs_old = ex['questions']
    old_count = len(qs_old)
    old_math = sum(1 for q in qs_old if '$' in q['prompt'])
    if old_count and old_math / old_count >= 0.10:
        print(f'[{idx+1}/{len(pdfs)}] SKIP (already has math {old_math}/{old_count}): {title}', flush=True)
        continue

    print(f'[{idx+1}/{len(pdfs)}] PARSING {fname} (old {old_count} Qs, math {old_math})', flush=True)
    pdf_path = os.path.join(PAPERS_DIR, fname)
    try:
        qs = parse_pdf_local(pdf_path)
    except Exception as e:
        print(f'  PARSE FAILED: {e}', flush=True)
        report.append({'title': title, 'status': 'parse_failed', 'error': str(e)[:200]})
        continue

    new_count = len(qs)
    print(f'  parsed {new_count} Qs (old {old_count})', flush=True)
    if new_count < 35 and new_count <= old_count:
        print('  NOT patching (too few and not better than old)', flush=True)
        report.append({'title': title, 'status': 'skipped_few', 'new': new_count, 'old': old_count})
        continue

    payload = {
        'title': title,
        'settings_confirmed': True,
        'gate_branch': branch,
        'questions': [to_authoring(q, i) for i, q in enumerate(qs)],
    }
    resp = httpx.patch(f'{API}/exams/{exam["id"]}', json=payload, headers=h, timeout=300)
    print(f'  PATCH {resp.status_code} ({new_count} Qs)', flush=True)
    report.append({'title': title, 'status': 'patched' if resp.status_code == 200 else 'patch_failed',
                   'new': new_count, 'old': old_count, 'code': resp.status_code})
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    time.sleep(2)

print('\n=== BATCH DONE ===', flush=True)
print(json.dumps(collections.Counter(r['status'] for r in report), indent=2), flush=True)
