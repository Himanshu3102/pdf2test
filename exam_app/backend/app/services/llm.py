import json
import re
import httpx
from app.config import settings


class LLMError(Exception):
    pass


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


def _is_anthropic(base_url: str) -> bool:
    return "anthropic" in base_url.lower()


def chat_completion(messages: list[dict], max_tokens: int | None = None, json_mode: bool = False, temperature: float = 0.2, timeout: int | None = None) -> str:
    key, base_url, model = _active()
    if not key:
        raise LLMError("LLM provider not configured (missing API key).")
    max_tok = max_tokens or settings.LLM_MAX_OUTPUT_TOKENS
    to = timeout or settings.LLM_TIMEOUT_SECONDS
    if _is_anthropic(base_url):
        return _anthropic_completion(key, base_url, model, messages, max_tok, json_mode, temperature, to)
    return _openai_completion(key, base_url, model, messages, max_tok, json_mode, temperature, to)


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
        raise LLMError(f"LLM provider error {r.status_code}: {r.text[:500]}")
    try:
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"Malformed LLM response: {e}")


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
