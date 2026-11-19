import fitz, re, sys, time, httpx, os
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')

from app.services import pdf_extraction
from app.services.parser import parse_pdf_with_vision, extract_answer_key

API = 'http://13.233.27.70/api/v1'
PAPERS_DIR = r'C:\Users\himan\Desktop\pdf2test\previous papers'
YEARS = [2024, 2025, 2026]

r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}

papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=20).json()


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
        chunk = r'C:\Users\himan\Desktop\pdf2test\_da_chunk.pdf'
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
                print(f'    pages {start+1}-{end} attempt {attempt+1} failed: {str(e)[:80]}', flush=True)
                time.sleep(6)
        if not ok:
            print(f'    pages {start+1}-{end}: FAILED', flush=True)

    # Apply answer keys + clean prompts
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


for year in YEARS:
    title = f'GATE {year} - Data Science and Artificial Intelligence'
    paper = next((p for p in papers if p['branch'] == 'DA' and p['title'] == title and p.get('exam_id')), None)
    if not paper:
        print(f'[{year}] no DA paper with exam found, skipping')
        continue
    exam_id = paper['exam_id']
    pdf_path = os.path.join(PAPERS_DIR, f'GATE AI {year} Question Paper with Answer Key.pdf')
    if not os.path.exists(pdf_path):
        print(f'[{year}] PDF missing: {pdf_path}')
        continue

    print(f'\n=== {year}: {title} (exam {exam_id}) ===', flush=True)
    qs = parse_pdf_local(pdf_path)
    print(f'  parsed {len(qs)} questions', flush=True)
    if len(qs) < 30:
        print('  too few questions, NOT patching')
        continue

    payload = {
        'title': title,
        'settings_confirmed': True,
        'gate_branch': 'DA',
        'questions': [to_authoring(q, i) for i, q in enumerate(qs)],
    }
    resp = httpx.patch(f'{API}/exams/{exam_id}', json=payload, headers=h, timeout=180)
    print(f'  PATCH {resp.status_code}: {len(qs)} questions', flush=True)
    if resp.status_code != 200:
        print('  body:', resp.text[:300], flush=True)
