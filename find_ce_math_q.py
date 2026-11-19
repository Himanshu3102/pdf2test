import httpx

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}
ps = httpx.get(f'{API}/gate/papers', headers=h, params={'branch': 'CE'}, timeout=20).json()
for p in ps:
    if p['title'] == 'GATE 2016 - Civil Engineering' and p.get('exam_id'):
        ex = httpx.get(f"{API}/exams/{p['exam_id']}", headers=h, timeout=30).json()
        for i, q in enumerate(ex['questions']):
            if '$' in q['prompt'] and len(q['prompt']) > 50:
                print('index', i, '| Q', i+1)
                print(q['prompt'][:200].replace('\n', ' '))
                print('opts:', [o['text'][:50] for o in q['options'][:2]])
                break
        break
