import httpx, collections

API = 'http://13.233.27.70/api/v1'
r = httpx.post(f'{API}/auth/login', json={'username': 'gateadmin', 'password': 'gateadmin123'}, timeout=10)
h = {'Authorization': 'Bearer ' + r.json()['access_token']}

ps = httpx.get(f'{API}/gate/papers', headers=h, timeout=20).json()
print('Library total:', len(ps))
by_title = collections.Counter(p['title'] for p in ps)
dups = {t: c for t, c in by_title.items() if c > 1}
print('Duplicate titles:', len(dups))
for t, c in list(dups.items())[:10]:
    print(' ', c, t)

exams = httpx.get(f'{API}/me/exams', headers=h, timeout=20).json()
print('Exams total:', len(exams), collections.Counter(e['status'] for e in exams))
et = collections.Counter(e['title'] for e in exams)
edups = {t: c for t, c in et.items() if c > 1}
print('Duplicate exam titles:', len(edups))
for t, c in list(edups.items())[:10]:
    print(' ', c, t)
