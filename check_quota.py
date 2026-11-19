import sys, httpx, base64, fitz
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings

key = settings.GEMINI_API_KEY
base = settings.GEMINI_BASE_URL.rstrip('/')
doc = fitz.open(r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf')
page = doc[0]
scale = 600 / max(page.rect.width, 1)
pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
img = 'data:image/jpeg;base64,' + base64.b64encode(pix.tobytes('jpeg')).decode('ascii')
doc.close()
payload = {'model': settings.GEMINI_MODEL, 'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'hi'}, {'type': 'image_url', 'image_url': {'url': img}}]}], 'max_tokens': 10}
r = httpx.post(base + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=30)
print(r.status_code)
print(r.text[:400])
