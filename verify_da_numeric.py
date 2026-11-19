import httpx

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}
papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=20).json()
for p in papers:
    if p['branch'] != 'DA' or not p.get('exam_id'):
        continue
    exam = httpx.get(f"{API}/exams/{p['exam_id']}", headers=h, timeout=30).json()
    nums = [q for q in exam['questions'] if q['qtype'] == 'numeric']
    print(p['year'], '| numeric:', len(nums))
    for q in nums[:3]:
        print('  key:', repr(q['answer_key']), '| tol:', q['tolerance'], '|', q['prompt'][:50].replace('\n', ' '))
    bad = [q for q in nums if not isinstance(q['answer_key'], (int, float))]
    print('  non-float keys:', len(bad))
