import httpx

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}
ps = httpx.get(f'{API}/gate/papers', headers=h, params={'branch': 'CE'}, timeout=20).json()
for p in ps:
    if p.get('exam_id') and '2016' in p['title']:
        ex = httpx.get(f"{API}/exams/{p['exam_id']}", headers=h, timeout=30).json()
        qs = ex['questions']
        print(p['title'], '| lib_qs:', p['question_count'], '| actual_qs:', len(qs), '| math:', sum(1 for q in qs if '$' in q['prompt']), '| keys:', sum(1 for q in qs if q['answer_key'] is not None))
