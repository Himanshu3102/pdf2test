import httpx

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}
ps = httpx.get(f'{API}/gate/papers', headers=h, timeout=20).json()
for p in ps:
    if p['branch'] == 'DA' and p.get('exam_id'):
        ex = httpx.get(f"{API}/exams/{p['exam_id']}", headers=h, timeout=30).json()
        qs = ex['questions']
        print(p['year'], '| with key:', sum(1 for q in qs if q['answer_key'] is not None), '/', len(qs))
