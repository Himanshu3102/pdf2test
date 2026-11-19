import base64, json, sys, time
import fitz
import httpx

sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings
from app.services.parser import VISION_PARSE_SYSTEM

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
MODELS = ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-3-flash-preview', 'gemini-3.5-flash', 'gemini-flash-latest', 'gemini-flash-lite-latest']

key = settings.GEMINI_API_KEY
base = settings.GEMINI_BASE_URL.rstrip('/')

doc = fitz.open(PDF)
imgs = []
for i in range(10, 13):
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

for model in MODELS:
    payload = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 8192, "response_format": {"type": "json_object"}}
    t0 = time.time()
    try:
        r = httpx.post(base + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=180)
        dt = time.time() - t0
        if r.status_code != 200:
            print(f'{model:28s} {r.status_code} {dt:5.1f}s | {r.text[:120]}')
            continue
        data = r.json()
        ch = data.get('choices') or []
        if not ch:
            print(f'{model:28s} 200 {dt:5.1f}s | NO CHOICES | {json.dumps(data)[:150]}')
            continue
        msg = ch[0].get('message') or {}
        text = msg.get('content')
        fr = ch[0].get('finish_reason')
        print(f'{model:28s} 200 {dt:5.1f}s | finish={fr} | content_type={type(text).__name__} len={len(text) if text else 0} | usage={data.get("usage")}')
        if text:
            try:
                obj = json.loads(text)
                print('   parsed JSON, questions:', len(obj.get('questions') or []))
            except Exception as e:
                print('   JSON parse failed:', str(e)[:100], '| head:', text[:100])
        else:
            print('   message keys:', list(msg.keys()), '| choice keys:', list(ch[0].keys()))
    except Exception as e:
        print(f'{model:28s} EXC {time.time()-t0:5.1f}s | {type(e).__name__}: {str(e)[:120]}')
    time.sleep(2)
