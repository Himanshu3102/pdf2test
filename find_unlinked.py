import httpx, collections

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}

exams = httpx.get(f'{API}/me/exams', headers=h, timeout=30).json()
papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=30).json()
linked = {p['exam_id'] for p in papers if p.get('exam_id')}

print('exams:', len(exams), '| linked:', len(linked))
print('\nUNLINKED EXAMS:')
for e in sorted(exams, key=lambda x: x['title']):
    if e['id'] not in linked:
        # find candidate papers with same branch/year
        print(f"  {e['id'][:8]} | {e['status']:9s} | qs={e.get('question_count')} | branch={e.get('gate_branch')} | {e['title']}")
