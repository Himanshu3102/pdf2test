import base64, json, sys, time
import fitz, httpx
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings
from app.services.parser import VISION_PARSE_SYSTEM

# Test 400px vs 600px on pages 1-3 of CE 2016 Set 1
PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
key = settings.GEMINI_API_KEY
base = settings.GEMINI_BASE_URL.rstrip('/')

for width in [400, 600]:
    doc = fitz.open(PDF)
    imgs = []
    for i in range(0, 3):
        page = doc[i]
        scale = width / max(page.rect.width, 1)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        imgs.append('data:image/jpeg;base64,' + base64.b64encode(pix.tobytes('jpeg')).decode('ascii'))
    doc.close()
    content = [{"type": "text", "text": "Extract all questions from these pages. Return JSON only."}]
    for img in imgs:
        content.append({"type": "image_url", "image_url": {"url": img}})
    messages = [{"role": "system", "content": VISION_PARSE_SYSTEM}, {"role": "user", "content": content}]
    payload = {"model": settings.GEMINI_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 8192, "response_format": {"type": "json_object"}}
    t0 = time.time()
    try:
        r = httpx.post(base + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=180)
        dt = time.time() - t0
        if r.status_code != 200:
            print(f'width={width}: HTTP {r.status_code} {dt:.1f}s')
            continue
        text = r.json()['choices'][0]['message'].get('content') or ''
        obj = json.loads(text)
        print(f'width={width}: {dt:.1f}s, qs={len(obj.get("questions") or [])}, chars={len(text)}')
    except Exception as e:
        print(f'width={width}: {type(e).__name__} {str(e)[:80]}')
    time.sleep(2)
