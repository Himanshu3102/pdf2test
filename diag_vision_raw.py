import base64, json, sys
import fitz, httpx
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')
from app.config import settings
from app.services.parser import VISION_PARSE_SYSTEM
from app.services.llm import _active, _models_to_try, chat_json, LLMError

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
CHUNK = r'C:\Users\himan\Desktop\pdf2test\_test_chunk.pdf'

# chunk already exists; render its pages
doc = fitz.open(CHUNK)
imgs = []
for page in doc:
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

key, base, model = _active()
for candidate in _models_to_try(model, base)[:2]:
    payload = {"model": candidate, "messages": messages, "temperature": 0.2, "max_tokens": 8192, "response_format": {"type": "json_object"}}
    try:
        r = httpx.post(base.rstrip('/') + '/chat/completions', headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}, json=payload, timeout=300)
    except Exception as e:
        print(candidate, 'EXC', e)
        continue
    print('===', candidate, 'status', r.status_code)
    if r.status_code != 200:
        print(r.text[:200])
        continue
    data = r.json()
    ch = data['choices'][0]
    text = ch['message'].get('content') or ''
    print('finish:', ch.get('finish_reason'), '| usage:', data.get('usage'), '| len:', len(text))
    print('HEAD:', text[:200].replace('\n', ' '))
    print('TAIL:', text[-300:].replace('\n', ' '))
    try:
        obj = json.loads(text)
        print('PARSED OK, questions:', len(obj.get('questions') or []))
    except Exception as e:
        print('json.loads failed:', e)
        from app.services.llm import _fix_json_escapes
        try:
            obj = json.loads(_fix_json_escapes(text))
            print('fixed-parse OK, questions:', len(obj.get('questions') or []))
        except Exception as e2:
            print('fixed-parse failed:', e2)
    break
