import httpx, collections

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}

exams = httpx.get(f'{API}/me/exams', headers=h, timeout=30).json()
papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=30).json()

by_title = collections.defaultdict(list)
for e in exams:
    by_title[e['title']].append(e)

paper_by_exam = {}
for p in papers:
    if p.get('exam_id'):
        paper_by_exam.setdefault(p['exam_id'], []).append(p)

print('DUPLICATE EXAM GROUPS:')
for title, es in sorted(by_title.items()):
    if len(es) < 2:
        continue
    print(f'\n{title}')
    for e in sorted(es, key=lambda x: x['created_at']):
        linked = paper_by_exam.get(e['id'], [])
        print(f"  {e['id'][:8]} | {e['status']:10s} | qs={e.get('question_count')} | created={e['created_at'][:19]} | lib={len(linked)}")

print('\n\nORPHAN LIBRARY (no exam) DUPLICATES:')
pt = collections.defaultdict(list)
for p in papers:
    pt[p['title']].append(p)
for title, ps in sorted(pt.items()):
    if len(ps) > 1:
        print(f'\n{title}')
        for p in ps:
            print(f"  lib={p['id'][:8]} | exam={str(p.get('exam_id'))[:8]} | qs={p.get('question_count')} | status={p.get('status')}")
