import httpx

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}
papers = httpx.get(f'{API}/gate/papers', headers=h, timeout=20).json()
for p in papers:
    if p['branch'] == 'DA' and p.get('exam_id'):
        ats = httpx.get(f"{API}/exams/{p['exam_id']}/attempts", headers=h, timeout=20).json()
        print(p['title'], '| attempts:', len(ats))
