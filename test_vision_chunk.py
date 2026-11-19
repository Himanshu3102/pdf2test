import fitz, sys, time, collections
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.services.parser import parse_pdf_with_vision

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
CHUNK = r'C:\Users\himan\Desktop\pdf2test\_test_chunk.pdf'

src = fitz.open(PDF)
new = fitz.open()
for i in range(10, 15):
    new.insert_pdf(src, from_page=i, to_page=i)
new.save(CHUNK)
new.close()
src.close()

t0 = time.time()
res = parse_pdf_with_vision(CHUNK, workers=3)
print(f'elapsed {time.time()-t0:.1f}s | questions: {len(res.questions)}')
print('warnings:')
for w in res.warnings:
    print('  -', w)
print('by source_page:', collections.Counter(q.source_page for q in res.questions))
for q in res.questions[:3]:
    print(' Q', q.source_page, '|', q.prompt[:100].replace('\n', ' '))
    print('   opts:', [o.text[:35] for o in (q.options or [])])
