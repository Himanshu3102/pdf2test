import re, sys, time, httpx, os, json, collections, argparse
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')

from app.services.parser import parse_pdf_with_vision, extract_answer_key, _apply_answer_key

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

cli = argparse.ArgumentParser()
cli.add_argument('--start', type=int, default=0)
cli.add_argument('--limit', type=int, default=0)
args = cli.parse_args()

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
    res = parse_pdf_with_vision(pdf_path, workers=2, batch_size=5)
    questions = res.questions
    if questions and any(q.answer_key is None for q in questions):
        try:
            import fitz
            doc = fitz.open(pdf_path)
            full_text = '\n'.join(page.get_text() for page in doc)
            doc.close()
            ak = extract_answer_key(full_text)
            for i, q in enumerate(questions):
                if q.answer_key is None and (i + 1) in ak:
                    d = q.model_dump()
                    _apply_answer_key(d, ak[i + 1])
                    q.answer_key = d['answer_key']
                    q.qtype = d['qtype']
                    q.tolerance = d.get('tolerance')
        except Exception as e:
            print(f'    answer-key safety net failed: {e}', flush=True)
    return questions


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


def save_report(report):
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)


pdfs = sorted(f for f in os.listdir(PAPERS_DIR) if f.lower().endswith('.pdf'))
report = []
if os.path.exists(REPORT):
    try:
        report = json.load(open(REPORT, encoding='utf-8'))
    except Exception:
        report = []
done_titles = {r.get('title') for r in report if r.get('status') == 'patched'}

eligible = []
for fname in pdfs:
    info = parse_filename(fname)
    if not info:
        continue
    branch, year, set_num = info
    title = title_for(branch, year, set_num)
    es = by_title.get(title, [])
    if len(es) != 1:
        continue
    exam = es[0]
    if branch == 'DA':
        continue
    if title in done_titles:
        continue
    try:
        ex = httpx.get(f"{API}/exams/{exam['id']}", headers=h, timeout=60).json()
    except Exception:
        continue
    qs_old = ex['questions']
    old_count = len(qs_old)
    old_math = sum(1 for q in qs_old if '$' in q['prompt'])
    if old_count and old_math / old_count >= 0.10:
        continue
    eligible.append((fname, exam, title, branch, old_count, old_math))

eligible = eligible[args.start:]
if args.limit:
    eligible = eligible[:args.limit]
print(f'Eligible: {len(eligible)} papers (start={args.start} limit={args.limit})', flush=True)

for idx, (fname, exam, title, branch, old_count, old_math) in enumerate(eligible):
    print(f'[{idx+1}/{len(eligible)}] PARSING {fname} (old {old_count} Qs, math {old_math})', flush=True)
    pdf_path = os.path.join(PAPERS_DIR, fname)
    t0 = time.time()
    try:
        qs = parse_pdf_local(pdf_path)
    except Exception as e:
        print(f'  PARSE FAILED after {time.time()-t0:.0f}s: {e}', flush=True)
        report.append({'title': title, 'status': 'parse_failed', 'error': str(e)[:300]})
        save_report(report)
        continue

    new_count = len(qs)
    with_key = sum(1 for q in qs if q.answer_key is not None)
    math = sum(1 for q in qs if '$' in q.prompt)
    print(f'  parsed {new_count} Qs in {time.time()-t0:.0f}s | math {math} | keys {with_key}', flush=True)
    if new_count < 35 and new_count <= old_count:
        print('  NOT patching (too few and not better than old)', flush=True)
        report.append({'title': title, 'status': 'skipped_few', 'new': new_count, 'old': old_count})
        save_report(report)
        continue

    payload = {
        'title': title,
        'settings_confirmed': True,
        'gate_branch': branch,
        'questions': [to_authoring(q, i) for i, q in enumerate(qs)],
    }
    try:
        resp = httpx.patch(f'{API}/exams/{exam["id"]}', json=payload, headers=h, timeout=300)
        code = resp.status_code
        err = None if code == 200 else resp.text[:200]
    except Exception as e:
        code = None
        err = str(e)[:200]
    print(f'  PATCH {code} ({new_count} Qs){"" if err is None else " | " + err}', flush=True)
    report.append({'title': title, 'status': 'patched' if code == 200 else 'patch_failed',
                   'new': new_count, 'old': old_count, 'math': math, 'keys': with_key,
                   'code': code, 'error': err})
    save_report(report)
    time.sleep(2)

print('\n=== BATCH DONE ===', flush=True)
print(json.dumps(collections.Counter(r['status'] for r in report), indent=2), flush=True)
