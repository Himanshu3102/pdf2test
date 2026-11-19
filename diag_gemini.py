import base64, json, sys, os
import fitz
import httpx

sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings
from app.services.parser import VISION_PARSE_SYSTEM

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'

key = settings.GEMINI_API_KEY
base = settings.GEMINI_BASE_URL.rstrip('/')
model = settings.GEMINI_MODEL

# list models
try:
    r = httpx.get(base + '/models', headers={'Authorization': f'Bearer {key}'}, timeout=30)
    print('models status:', r.status_code)
    if r.status_code == 200:
        names = [m.get('id') for m in r.json().get('data', [])]
        print('models:', names)
    else:
        print(r.text[:300])
except Exception as e:
    print('model list failed:', e)

# render pages 11-15 (1-based) -> indexes 10..14
doc = fitz.open(PDF)
imgs = []
for i in range(10, 15):
    page = doc[i]
    scale = 600 / max(page.rect.width, 1)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    imgs.append('data:image/jpeg;base64,' + base64.b64encode(pix.tobytes('jpeg')).decode('ascii'))
doc.close()

content = [{"type": "text", "text": "Extract all questions from these pages. Return JSON only."}]
for img in imgs:
    content.append({"type": "image_url", "image_url": {"url": img}})
messages = [
    {"role": "system", "content": VISION_PARSE_SYSTEM},
    {"role": "user", "content": content},
]
payload = {
    "model": model,
    "messages": messages,
    "temperature": 0.2,
    "max_tokens": 8192,
    "response_format": {"type": "json_object"},
}
print('\nrequest bytes:', len(json.dumps(payload)))
try:
    r = httpx.post(base + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=300)
    print('status:', r.status_code)
    print('body head:', r.text[:400].replace('\n', ' '))
    if r.status_code == 200:
        data = r.json()
        print('top keys:', list(data.keys()))
        ch = data.get('choices') or []
        print('choices:', len(ch))
        if ch:
            print('choice0 keys:', list(ch[0].keys()))
            msg = ch[0].get('message') or {}
            print('message keys:', list(msg.keys()))
            print('finish_reason:', ch[0].get('finish_reason'))
            print('content type:', type(msg.get('content')).__name__, 'len:', len(msg.get('content') or ''))
            print('usage:', data.get('usage'))
except Exception as e:
    print('request failed:', type(e).__name__, str(e)[:300])
