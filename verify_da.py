import httpx, re

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}

papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=20).json()
for p in papers:
    if p['branch'] != 'DA' or not p.get('exam_id'):
        continue
    exam = httpx.get(f"{API}/exams/{p['exam_id']}", headers=h, timeout=30).json()
    qs = exam['questions']
    dollar = sum(1 for q in qs if '$' in q['prompt'])
    matrices = sum(1 for q in qs if 'matrix' in q['prompt'] or 'pmatrix' in q['prompt'] or 'bmatrix' in q['prompt'])
    prefixes = sum(1 for q in qs if q['prompt'].lstrip().startswith('. MCQ'))
    print(f"{p['year']}: {len(qs)} Qs | math={dollar} | matrices={matrices} | prefix={prefixes}")
    if qs:
        print('  Q1:', qs[0]['prompt'][:160].replace('\n', ' '))
        print('  opts:', [o['text'][:40] for o in qs[0]['options'][:2]])
