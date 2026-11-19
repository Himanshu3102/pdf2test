import sys
sys.path.insert(0, r'C:\Users\himan\Desktop\pdf2test\exam_app\backend')

from app.config import settings
from app.services.llm import is_configured, _active, _models_to_try, chat_json

key, base, model = _active()
print('configured:', is_configured())
print('models:', _models_to_try(model, base))
print('fallback setting:', settings.GEMINI_FALLBACK_MODELS)

r = chat_json([{'role': 'user', 'content': 'Return JSON: {"ok": true}'}], max_tokens=200)
print('chat_json:', r)
