import httpx, re

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}

r = httpx.get(f'{API}/gate/papers', params={'branch': 'DA'}, headers=h, timeout=10)
papers = [p for p in r.json() if p.get('exam_id')]

for p in papers:
    exam = httpx.get(f"{API}/exams/{p['exam_id']}", headers=h, timeout=30).json()
    qs = exam['questions']
    dollar = sum(1 for q in qs if '$' in q['prompt'])
    matrix = sum(1 for q in qs if 'begin{' in q['prompt'] or 'matrix' in q['prompt'].lower())
    frac = sum(1 for q in qs if 'frac' in q['prompt'])
    print(p['year'], p['title'])
    print('  Qs:', len(qs), '| with $..$:', dollar, '| matrix:', matrix, '| frac:', frac)
    shown = 0
    for q in qs:
        if ('matrix' in q['prompt'].lower() or 'frac' in q['prompt']) and shown < 2:
            print('  SAMPLE:', q['prompt'][:260].replace('\n', ' '))
            shown += 1
    print()
