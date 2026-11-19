import os, re, httpx, collections

API = 'http://13.233.27.70/api/v1'
PAPERS_DIR = r'C:\Users\himan\Desktop\pdf2test\previous papers'

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


pdfs = sorted(f for f in os.listdir(PAPERS_DIR) if f.lower().endswith('.pdf'))
matched, unmatched = [], []
for f in pdfs:
    info = parse_filename(f)
    if not info:
        unmatched.append((f, 'filename'))
        continue
    branch, year, set_num = info
    set_str = f' Set {set_num}' if set_num > 1 else ''
    title = f'GATE {year}{set_str} - {BRANCH_NAMES[branch]}'
    es = by_title.get(title, [])
    if not es:
        # try with Set 1 explicitly
        alt = f'GATE {year} Set 1 - {BRANCH_NAMES[branch]}'
        es = by_title.get(alt, [])
        title = alt
    if len(es) == 1:
        matched.append((f, title, es[0]['id'], es[0]['question_count']))
    elif len(es) > 1:
        unmatched.append((f, f'duplicate exam title: {title}'))
    else:
        unmatched.append((f, f'no exam for: {title}'))

print('PDFs:', len(pdfs), '| matched:', len(matched), '| unmatched:', len(unmatched))
for f, why in unmatched:
    print('  UNMATCHED:', f, '->', why)
print('\nMatched sample:')
for row in matched[:5]:
    print(' ', row)
