"""Provider clients. Thin on purpose: one JSON-in/JSON-out call, strict parsing, no content logging.

Providers: Gemini (native API) and any OpenAI-compatible endpoint (Groq, OpenRouter, Cloudflare, ...).
Model names and free-tier limits change often, so nothing is hardcoded: AI_MODEL is required.
"""
import json
import logging
import re
import time

import httpx

log = logging.getLogger("worker.ai")


class LLMError(Exception):
    """`code` is safe to store and show; the message never contains prompts or responses."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail  # e.g. "400:model_not_found" or "ConnectError": safe to log, contains no content


def extract_json(text: str) -> dict:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.I)
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        raise LLMError("bad_response")
    try:
        obj = json.loads(t[i: j + 1])
    except ValueError:
        raise LLMError("bad_response")
    if not isinstance(obj, dict):
        raise LLMError("bad_response")
    return obj


def _detail(r: "httpx.Response") -> str:
    """HTTP status plus the provider's short error code if it has one. Never the message text."""
    d = str(r.status_code)
    try:
        err = r.json().get("error") or {}
        code = str(err.get("code") or err.get("type") or "")
        if re.fullmatch(r"[\w.-]{1,40}", code):
            d += ":" + code
    except Exception:
        pass
    return d


def _retry_after(r: "httpx.Response"):
    try:
        return float(r.headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


class _Base:
    name = "base"

    def __init__(self, model: str, client: httpx.Client | None = None, sleep=time.sleep, timeout: float = 25.0):
        self.model = model
        self.client = client or httpx.Client(timeout=timeout)
        self.sleep = sleep

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        for attempt in range(3):
            try:
                r = self.client.post(url, headers=headers, json=body)
            except httpx.TimeoutException:
                if attempt == 2:
                    raise LLMError("timeout", "timeout")
                self.sleep(1 + attempt)
                continue
            except httpx.HTTPError as e:
                raise LLMError("provider_error", type(e).__name__)  # e.g. ConnectError: the container cannot reach the provider
            if r.status_code in (401, 403):
                raise LLMError("auth", _detail(r))
            if r.status_code == 429:
                # A free-tier limit usually resets per minute: waiting would only slow the user down, so fall back at once
                # unless the provider says the wait is very short.
                wait = _retry_after(r)
                if wait is not None and wait <= 3 and attempt < 2:
                    self.sleep(wait)
                    continue
                raise LLMError("rate_limited", _detail(r))
            if r.status_code >= 500:
                if attempt == 2:
                    raise LLMError("rate_limited" if r.status_code == 429 else "provider_error", _detail(r))
                self.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                raise LLMError("provider_error", _detail(r))
            try:
                return r.json()
            except ValueError:
                raise LLMError("bad_response")
        raise LLMError("provider_error")


class GeminiLLM(_Base):
    name = "gemini"

    def __init__(self, api_key: str, model: str, **kw):
        super().__init__(model, **kw)
        self.key = api_key

    def complete_json(self, system: str, user: str, max_tokens: int = 1200) -> dict:
        data = self._post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            {"x-goog-api-key": self.key},  # header, not URL: keys in URLs end up in logs
            {"systemInstruction": {"parts": [{"text": system}]},
             "contents": [{"role": "user", "parts": [{"text": user}]}],
             "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}})
        try:
            cand = data["candidates"][0]
            text = "".join(p.get("text", "") for p in cand["content"]["parts"])
        except (KeyError, IndexError, TypeError):
            raise LLMError("blocked")
        return extract_json(text)


class OpenAICompatLLM(_Base):
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, reasoning_effort: str | None = None, **kw):
        super().__init__(model, **kw)
        self.base, self.key, self.effort = base_url.rstrip("/"), api_key, reasoning_effort

    def complete_json(self, system: str, user: str, max_tokens: int = 1200) -> dict:
        body = {"model": self.model, "temperature": 0.2, "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.effort:  # only sent when asked for: models that don't support it would reject the request
            body["reasoning_effort"] = self.effort
        data = self._post(f"{self.base}/chat/completions", {"Authorization": f"Bearer {self.key}"}, body)
        try:
            choice = data["choices"][0]
            text = choice["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LLMError("bad_response")
        if choice.get("finish_reason") == "length":  # reasoning models can spend the whole budget on thinking
            raise LLMError("truncated")
        return extract_json(text)


PRESETS = {"groq": "https://api.groq.com/openai/v1"}


def load_llm(env) -> "_Base | None":
    """None means AI is off; the product then runs entirely on deterministic logic.

    Every value is trimmed: a stray space after a key or a model name in .env otherwise causes confusing 401/404 errors.
    """
    def get(k: str) -> str:
        return (env.get(k) or "").strip()

    provider = get("AI_PROVIDER").lower() or "none"
    if provider == "none":
        return None
    key, model = get("AI_API_KEY"), get("AI_MODEL")
    if not key or not model:
        log.error("ai_misconfigured provider=%s missing=%s", provider, "key" if not key else "model")
        return None
    if provider == "gemini":
        return GeminiLLM(key, model)
    base = get("AI_BASE_URL") or PRESETS.get(provider)
    effort = get("AI_REASONING_EFFORT").lower() or None
    if effort not in (None, "low", "medium", "high"):
        log.error("ai_misconfigured AI_REASONING_EFFORT must be low, medium or high")
        effort = None
    if provider in ("groq", "openai_compatible") and base:
        return OpenAICompatLLM(base, key, model, reasoning_effort=effort)
    log.error("ai_misconfigured provider=%s", provider)
    return None
