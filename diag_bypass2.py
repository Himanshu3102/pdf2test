import base64, json, sys
import fitz, httpx
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings
from app.services.parser import VISION_PARSE_SYSTEM
from app.services.llm import _active

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
PAGE = 14
key, base, model = _active()

doc = fitz.open(PDF)
page = doc[PAGE]
rect = page.rect
text = page.get_text()
doc.close()


def render_clip(y0, y1, width=600):
    doc = fitz.open(PDF)
    page = doc[PAGE]
    rect = page.rect
    clip = fitz.Rect(rect.x0, rect.y0 + rect.height * y0, rect.x1, rect.y0 + rect.height * y1)
    scale = width / max(rect.width, 1)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip)
    data = pix.tobytes('jpeg')
    doc.close()
    return 'data:image/jpeg;base64,' + base64.b64encode(data).decode('ascii')


def post(payload):
    r = httpx.post(base.rstrip('/') + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=300)
    if r.status_code != 200:
        return f'HTTP {r.status_code}: {r.text[:100]}'
    ch = r.json()['choices'][0]
    txt = ch['message'].get('content') or ''
    fr = ch.get('finish_reason')
    if not txt:
        return f'EMPTY {fr}'
    try:
        obj = json.loads(txt)
        return f'OK qs={len(obj.get("questions") or [])}'
    except Exception as e:
        return f'BADJSON len={len(txt)} {e}'


def vision(img, prompt="Extract all questions from this page. Return JSON only."):
    return {"model": model, "messages": [
        {"role": "system", "content": VISION_PARSE_SYSTEM},
        {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img}}]},
    ], "temperature": 0.2, "max_tokens": 8192, "response_format": {"type": "json_object"}}


print('--- half-page crops ---')
for label, (a, b) in {'top': (0.06, 0.55), 'bottom': (0.45, 0.95), 'q48': (0.06, 0.52), 'q49': (0.50, 0.95)}.items():
    print(f'{label:7s}', post(vision(render_clip(a, b))))

print('\n--- text-only call ---')
txt_prompt = f"""Extract all questions from this exam page text. Return JSON only.
Preserve the wording. Use LaTeX ($...$) for mathematical expressions where identifiable.

PAGE TEXT:
{text}"""
payload = {"model": model, "messages": [
    {"role": "system", "content": VISION_PARSE_SYSTEM},
    {"role": "user", "content": txt_prompt},
], "temperature": 0.2, "max_tokens": 8192, "response_format": {"type": "json_object"}}
print(post(payload))
