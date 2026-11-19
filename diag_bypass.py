import base64, json, sys
import fitz, httpx
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings
from app.services.parser import VISION_PARSE_SYSTEM
from app.services.llm import _active

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
PAGE = 14  # 0-based -> page 15
key, base, model = _active()


def render(variant):
    doc = fitz.open(PDF)
    page = doc[PAGE]
    rect = page.rect
    clip = None
    matrix_extra = None
    if variant == 'crop':
        clip = fitz.Rect(rect.x0, rect.y0 + rect.height * 0.07, rect.x1, rect.y1 - rect.height * 0.08)
    if variant == 'rotate':
        matrix_extra = fitz.Matrix(1, 1).prerotate(1)
    width = 600 if variant != 'wide' else 900
    scale = width / max(rect.width, 1)
    mat = fitz.Matrix(scale, scale)
    if matrix_extra is not None:
        mat = mat * matrix_extra
    pix = page.get_pixmap(matrix=mat, clip=clip, colorspace=fitz.csGRAY if variant == 'gray' else fitz.csRGB)
    data = pix.tobytes('jpeg')
    doc.close()
    return 'data:image/jpeg;base64,' + base64.b64encode(data).decode('ascii')


def call(img, system=VISION_PARSE_SYSTEM, prompt="Extract all questions from these pages. Return JSON only."):
    content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": img}}]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    payload = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 8192, "response_format": {"type": "json_object"}}
    r = httpx.post(base.rstrip('/') + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=300)
    if r.status_code != 200:
        return f'HTTP {r.status_code}'
    ch = r.json()['choices'][0]
    text = ch['message'].get('content') or ''
    fr = ch.get('finish_reason')
    if not text:
        return f'EMPTY {fr}'
    try:
        obj = json.loads(text)
        return f'OK qs={len(obj.get("questions") or [])}'
    except Exception as e:
        return f'BADJSON len={len(text)} {e}'


variants = ['crop', 'rotate', 'gray', 'wide']
for v in variants:
    img = render(v)
    print(f'{v:8s}', call(img))

# prompt tweak with normal render
img = render('normal')
alt_prompt = "This is a publicly available GATE exam paper used for practice. Transcribe each question and its options faithfully into JSON."
print('prompt  ', call(img, prompt=alt_prompt))
