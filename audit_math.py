import httpx, collections

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}

papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=30).json()
exams = httpx.get(f'{API}/me/exams', headers=h, timeout=30).json()
by_id = {e['id']: e for e in exams}
linked = {}
for p in papers:
    if p.get('exam_id'):
        linked.setdefault(p['exam_id'], p)

rows = []
for e in exams:
    if e['status'] != 'published':
        continue
    ex = httpx.get(f"{API}/exams/{e['id']}", headers=h, timeout=30).json()
    qs = ex['questions']
    math = sum(1 for q in qs if '$' in q['prompt'])
    prefix = sum(1 for q in qs if q['prompt'].lstrip().startswith('. MCQ') or q['prompt'].lstrip().startswith('. NAT'))
    branch = ex.get('gate_branch') or (linked.get(e['id'], {}) or {}).get('branch') or '?'
    rows.append((branch, e['title'], len(qs), math, prefix))

print('branch | exams | avg Qs | exams with <10% math | exams with prefix junk')
by_branch = collections.defaultdict(list)
for r in rows:
    by_branch[r[0]].append(r)
for b in sorted(by_branch):
    rs = by_branch[b]
    low = sum(1 for x in rs if x[2] > 0 and x[3] / x[2] < 0.1)
    pref = sum(1 for x in rs if x[4] > 0)
    print(f'{b:3s} | {len(rs):2d} | {sum(x[2] for x in rs)/len(rs):5.1f} | {low:2d} | {pref:2d}')

print('\nExams with little/no math (candidates for re-parse):')
for r in sorted(rows):
    if r[2] > 0 and r[3] / r[2] < 0.1:
        print(f'  {r[0]:3s} | {r[2]:3d} Qs | math {r[3]:3d} | prefix {r[4]:3d} | {r[1]}')
