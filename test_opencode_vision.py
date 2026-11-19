import base64, json, sys
import fitz, httpx

# Test OpenCode Go vision support
KEY = "oc_sk_ac2a03e41a7a_OGbd1KmQsJ16JJsIHUWpTGOiQrVGiV8t"
BASE = "https://opencode.ai/inference/anthropic/v1"
MODEL = "qwen3.8-flash"

PDF = r'C:\Users\himan\Desktop\pdf2test\previous papers\GATE CE 2016 Set 1 Question Paper with Answer Key.pdf'
doc = fitz.open(PDF)
page = doc[0]
scale = 600 / max(page.rect.width, 1)
pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
img = 'data:image/jpeg;base64,' + base64.b64encode(pix.tobytes('jpeg')).decode('ascii')
doc.close()

# Anthropic messages format with image
payload = {
    "model": MODEL,
    "max_tokens": 500,
    "messages": [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img.split(',')[1]}},
            {"type": "text", "text": "How many questions are on this page? Reply with just a number."}
        ]
    }]
}
headers = {"x-api-key": KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
try:
    r = httpx.post(BASE.rstrip('/') + '/messages', headers=headers, json=payload, timeout=60)
    print('status:', r.status_code)
    print(r.text[:500])
except Exception as e:
    print('exc:', type(e).__name__, str(e)[:300])
