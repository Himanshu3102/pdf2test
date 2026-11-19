import sys, time, collections
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.services.parser import parse_pdf_with_vision

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
t0 = time.time()
res = parse_pdf_with_vision(PDF, workers=2, batch_size=5)
dt = time.time() - t0
qs = res.questions
print(f'elapsed {dt:.0f}s | questions {len(qs)}')
print('types:', collections.Counter(q.qtype for q in qs))
print('with key:', sum(1 for q in qs if q.answer_key is not None))
print('with math:', sum(1 for q in qs if '$' in q.prompt))
print('warnings:', len(res.warnings))
for w in res.warnings:
    print('  -', w[:160])
print('\nfirst 3:')
for q in qs[:3]:
    print(' Q', q.source_page, q.qtype, '|', q.prompt[:110].replace('\n', ' '))
    print('   ans:', q.answer_key, '| opts:', [o.text[:35] for o in (q.options or [])][:4])
print('\nlast 3:')
for q in qs[-3:]:
    print(' Q', q.source_page, q.qtype, '|', q.prompt[:110].replace('\n', ' '))
    print('   ans:', q.answer_key)
