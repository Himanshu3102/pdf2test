import json
import re
import time
import logging
import httpx
from app.config import settings
from app.logging_config import get_logger, log_event

logger = get_logger("llm")


class LLMError(Exception):
    def __init__(self, message: str, status: int | None = None, recitation: bool = False):
        super().__init__(message)
        self.status = status
        self.recitation = recitation


def _is_anthropic(base_url: str) -> bool:
    return "anthropic" in base_url.lower()


def _models_to_try(primary: str, base_url: str) -> list[str]:
    """Primary model first, then configured fallbacks (Gemini only)."""
    models = [primary]
    if settings.GEMINI_API_KEY and "generativelanguage" in base_url.lower():
        for name in (settings.GEMINI_FALLBACK_MODELS or "").split(","):
            name = name.strip()
            if name and name not in models:
                models.append(name)
    return models


def _is_permanent(err: Exception) -> bool:
    """Auth/payload errors will fail for every model, so don't rotate."""
    if isinstance(err, LLMError) and err.status in (400, 401, 403):
        return True
    return False


def _active() -> tuple[str | None, str, str]:
    if settings.GEMINI_API_KEY:
        return settings.GEMINI_API_KEY, settings.GEMINI_BASE_URL, settings.GEMINI_MODEL
    if settings.OPENAI_API_KEY:
        return settings.OPENAI_API_KEY, settings.OPENAI_BASE_URL, settings.OPENAI_MODEL
    if settings.OPENCODE_GO_API_KEY:
        model = settings.OPENCODE_GO_MODEL or settings.OPENAI_MODEL
        return settings.OPENCODE_GO_API_KEY, settings.OPENCODE_GO_BASE_URL, model
    return None, "", ""


def is_configured() -> bool:
    key, _, _ = _active()
    return bool(key)


def chat_completion(messages: list[dict], max_tokens: int | None = None, json_mode: bool = False, temperature: float = 0.2, timeout: int | None = None) -> str:
    key, base_url, model = _active()
    if not key:
        raise LLMError("LLM provider not configured (missing API key).")
    max_tok = max_tokens or settings.LLM_MAX_OUTPUT_TOKENS
    to = timeout or settings.LLM_TIMEOUT_SECONDS
    models = _models_to_try(model, base_url)
    last_err: Exception | None = None
    for idx, candidate in enumerate(models):
        t0 = time.perf_counter()
        try:
            if _is_anthropic(base_url):
                result = _anthropic_completion(key, base_url, candidate, messages, max_tok, json_mode, temperature, to)
            else:
                result = _openai_completion(key, base_url, candidate, messages, max_tok, json_mode, temperature, to)
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            log_event(logger, "llm_call", provider=base_url, model=candidate, fallback_index=idx,
                        max_tokens=max_tok,
                        input_chars=sum(len(str(m.get("content", ""))) for m in messages),
                        output_chars=len(result), latency_ms=elapsed, success=True)
            return result
        except Exception as e:
            last_err = e
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            log_event(logger, "llm_call", level=logging.WARNING, provider=base_url, model=candidate,
                        fallback_index=idx, latency_ms=elapsed, success=False, error=str(e)[:300])
            if _is_permanent(e):
                raise
            if isinstance(e, LLMError) and e.recitation:
                # All Gemini models share the recitation filter; rotating wastes time.
                raise
            # Try the next model; if none left, raise the last error.
            continue
    raise last_err or LLMError("LLM request failed")


def _openai_completion(key, base_url, model, messages, max_tok, json_mode, temperature, timeout):
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tok,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, headers=headers, json=payload)
    except Exception as e:
        raise LLMError(f"LLM request failed: {e}")
    if r.status_code >= 400:
        raise LLMError(f"LLM provider error {r.status_code}: {r.text[:500]}", status=r.status_code)
    try:
        data = r.json()
    except Exception as e:
        raise LLMError(f"Malformed LLM response: {e}")
    if isinstance(data, dict) and data.get("error"):
        raise LLMError(f"LLM provider error: {str(data['error'])[:400]}")
    try:
        choice = (data.get("choices") or [])[0]
        message = choice.get("message") or {}
        content = message.get("content")
    except Exception as e:
        raise LLMError(f"Malformed LLM response: {e}")
    if not content:
        finish = choice.get("finish_reason")
        raise LLMError(
            f"Empty LLM response (finish_reason={finish}): {r.text[:300]}",
            recitation=bool(finish and "RECITATION" in str(finish).upper()),
        )
    return content


def _anthropic_completion(key, base_url, model, messages, max_tok, json_mode, temperature, timeout):
    # separate system messages
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    system = "\n".join(system_parts)
    if json_mode:
        system = (system + "\nReturn only valid JSON, no markdown.").strip()
    conv = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("role") in ("user", "assistant")]
    url = base_url.rstrip("/") + "/messages"
    payload = {
        "model": model,
        "messages": conv,
        "max_tokens": max_tok,
        "temperature": temperature,
    }
    if system:
        payload["system"] = system
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, headers=headers, json=payload)
    except Exception as e:
        raise LLMError(f"LLM request failed: {e}")
    if r.status_code >= 400:
        raise LLMError(f"LLM provider error {r.status_code}: {r.text[:500]}")
    try:
        data = r.json()
        # content is list of blocks
        blocks = data.get("content", [])
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        return "\n".join(texts)
    except Exception as e:
        raise LLMError(f"Malformed LLM response: {e}")


def _fix_json_escapes(text: str) -> str:
    # Escape stray backslashes that are not valid JSON escapes (common with LaTeX).
    # Valid JSON escapes are two chars: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX.
    # LaTeX commands like \times, \lambda, \begin must be escaped; but \t followed
    # by a space is a real tab escape.
    result = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            nxt = text[i + 1]
            valid = nxt in '"\\/bfnrtu'
            # If nxt is a letter that starts a valid escape but is followed by
            # another letter, it is a LaTeX command, not an escape.
            if valid and nxt.isalpha() and i + 2 < n and text[i + 2].isalpha():
                valid = False
            if valid:
                result.append(ch)
                result.append(nxt)
                i += 2
                continue
            result.append("\\\\")
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def chat_json(messages: list[dict], max_tokens: int | None = None, timeout: int | None = None) -> dict:
    content = chat_completion(messages, max_tokens=max_tokens, json_mode=True, timeout=timeout)
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    candidates = [text]
    # try to extract outer object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidates.append(text[start:end + 1])
    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            try:
                return json.loads(_fix_json_escapes(cand))
            except json.JSONDecodeError:
                continue
    raise LLMError("LLM returned invalid JSON.")
