import httpx

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}
papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=20).json()
for p in papers:
    if p['branch'] == 'DA' and p['year'] == 2024 and p.get('exam_id'):
        exam = httpx.get(f"{API}/exams/{p['exam_id']}", headers=h, timeout=30).json()
        for i, q in enumerate(exam['questions']):
            if 'pmatrix' in q['prompt'] or 'bmatrix' in q['prompt'] or 'frac' in q['prompt']:
                print('index', i, '| Q', i + 1)
                print(q['prompt'][:250].replace('\n', ' '))
                print('opts:', [o['text'][:80] for o in q['options']])
                break
        break
