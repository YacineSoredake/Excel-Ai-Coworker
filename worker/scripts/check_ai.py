"""One-command diagnosis of the AI setup: network, key, model list, and a tiny JSON test call.

    docker compose run --rm -v "${PWD}/worker/scripts:/srv/scripts:ro" worker python scripts/check_ai.py

Sends no workbook data. Prints the provider's own error text for this test call only (never your key).
"""
import json
import os
import sys

import httpx

PRESETS = {"groq": "https://api.groq.com/openai/v1"}


def show(r):
    print(f"   -> HTTP {r.status_code}")
    return r


def main():
    provider, key, model = (os.environ.get(k, "").strip() for k in ("AI_PROVIDER", "AI_API_KEY", "AI_MODEL"))
    provider = provider.lower()
    base = os.environ.get("AI_BASE_URL", "").strip() or PRESETS.get(provider, "")
    print(f"provider={provider or '(none)'}  model={model or '(empty)'}  key={'set' if key else 'MISSING'}  base={base or '(gemini native)'}")
    if provider in ("", "none"):
        sys.exit("AI_PROVIDER is none: nothing to check. Set it in .env and restart the worker.")
    if not key or not model:
        sys.exit("AI_API_KEY and AI_MODEL must both be set in .env.")
    c = httpx.Client(timeout=25)
    if provider == "gemini":
        print("\n1. Test call")
        try:
            r = show(c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers={"x-goog-api-key": key},
                            json={"contents": [{"role": "user", "parts": [{"text": 'Reply with JSON {"ok": true}'}]}],
                                  "generationConfig": {"responseMimeType": "application/json"}}))
            print("  ", r.text[:300])
        except httpx.HTTPError as e:
            sys.exit(f"   cannot reach Google from this container: {type(e).__name__}")
        return
    h = {"Authorization": f"Bearer {key}"}
    print("\n1. Can this container reach the provider, and is the key accepted?")
    try:
        r = show(c.get(f"{base}/models", headers=h))
    except httpx.HTTPError as e:
        sys.exit(f"   NO: {type(e).__name__}. The container cannot reach {base} (DNS, proxy or firewall). Fix the network first.")
    if r.status_code in (401, 403):
        sys.exit("   The key was rejected. Create a new key and check there are no spaces or quotes around it in .env.")
    ids = sorted(m["id"] for m in r.json().get("data", [])) if r.status_code == 200 else []
    print(f"   {len(ids)} models available to this key")
    print("\n2. Is your AI_MODEL in that list?")
    if ids:
        print("   yes" if model in ids else f"   NO. '{model}' is not available. Models you can use:\n     " + "\n     ".join(ids))
    print("\n3. Tiny JSON test call with your model")
    body = {"model": model, "max_tokens": 200, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": 'Reply with JSON {"ok": true}'}]}
    effort = (os.environ.get("AI_REASONING_EFFORT") or "").strip().lower()
    if effort:
        body["reasoning_effort"] = effort
        print(f"   (using reasoning_effort={effort})")
    r = show(c.post(f"{base}/chat/completions", headers=h, json=body))
    try:
        body = r.json()
        if r.status_code == 200:
            ch = body["choices"][0]
            print("   finish_reason:", ch.get("finish_reason"), "| content:", (ch["message"].get("content") or "")[:120])
            if ch.get("finish_reason") == "length":
                print("   The model used its whole budget before answering (a reasoning model). Add AI_REASONING_EFFORT=low to .env, or choose another model.")
        else:
            print("   provider says:", json.dumps(body.get("error", body))[:400])
    except Exception:
        print("  ", r.text[:300])


if __name__ == "__main__":
    main()
