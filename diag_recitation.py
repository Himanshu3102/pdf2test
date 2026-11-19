import base64, json, sys
import fitz, httpx
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings
from app.services.parser import VISION_PARSE_SYSTEM
from app.services.llm import _active, _models_to_try

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
key, base, model = _active()
models = _models_to_try(model, base)


def render(pdf, pages):
    doc = fitz.open(pdf)
    imgs = []
    for i in pages:
        page = doc[i]
        scale = 600 / max(page.rect.width, 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        imgs.append('data:image/jpeg;base64,' + base64.b64encode(pix.tobytes('jpeg')).decode('ascii'))
    doc.close()
    return imgs


def call(imgs, m):
    content = [{"type": "text", "text": "Extract all questions from these pages. Return JSON only."}]
    for img in imgs:
        content.append({"type": "image_url", "image_url": {"url": img}})
    messages = [{"role": "system", "content": VISION_PARSE_SYSTEM}, {"role": "user", "content": content}]
    payload = {"model": m, "messages": messages, "temperature": 0.2, "max_tokens": 8192, "response_format": {"type": "json_object"}}
    r = httpx.post(base.rstrip('/') + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=300)
    if r.status_code != 200:
        return f'HTTP {r.status_code}: {r.text[:90]}'
    d = r.json()
    ch = d['choices'][0]
    text = (ch['message'].get('content') or '')
    fr = ch.get('finish_reason')
    if not text:
        return f'EMPTY finish={fr}'
    try:
        obj = json.loads(text)
        return f'OK finish={fr} qs={len(obj.get("questions") or [])}'
    except Exception as e:
        return f'BADJSON finish={fr} len={len(text)} {e}'


print('--- 5-page chunk (11-15) across models ---')
imgs5 = render(PDF, range(10, 15))
for m in models:
    print(f'{m:28s}', call(imgs5, m))

print('\n--- single pages across models ---')
for i in range(10, 15):
    img = render(PDF, [i])
    row = []
    for m in models:
        row.append(f'{m.split("/")[-1]}={call(img, m)}')
    print(f'page {i+1}:', ' | '.join(row))
