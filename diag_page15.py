import fitz

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
doc = fitz.open(PDF)
for i in [13, 14]:
    t = doc[i].get_text()
    print(f'===== PAGE {i+1} | chars {len(t)} | images {len(doc[i].get_images())} =====')
    print(t[:1200])
    print('...')
doc.close()
