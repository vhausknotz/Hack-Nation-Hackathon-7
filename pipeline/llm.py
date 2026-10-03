"""Azure OpenAI (Foundry) client with an on-disk cache and token accounting.

Every call is cached by (model, messages, options), so reruns cost nothing, and every real call
appends its token usage to data/cache/llm_usage.jsonl, so cost per task is measured, not guessed.
Auth: Entra ID through the local Azure login (see AGENTS.md).
"""

import hashlib
import json
import time
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "llm"
USAGE = ROOT / "data" / "cache" / "llm_usage.jsonl"
BASE_URL = "https://valiopenai.cognitiveservices.azure.com/openai/v1/"
# USD per 1M tokens (input, output), from the Azure pricing pages; used only for the usage log
PRICES = {"gpt-6-luna": (0.10, 0.50)}

_client = None
_usage_lock = threading.Lock()


def log_usage(entry):
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    with _usage_lock:
        with open(USAGE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def client():
    global _client
    if _client is None:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import OpenAI

        token = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
        _client = OpenAI(base_url=BASE_URL, api_key=token, max_retries=5, timeout=180)
    return _client


def chat(model: str, messages: list[dict], task: str, json_mode: bool = False, **options) -> str:
    """Return the model's reply text. `task` labels the call in the usage log (e.g. "cluster-names")."""
    key_material = json.dumps({"model": model, "messages": messages, "json": json_mode, "options": options}, sort_keys=True)
    key = hashlib.sha256(key_material.encode()).hexdigest()
    path = CACHE / key[:2] / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["content"]
    kwargs = dict(model=model, messages=messages, **options)
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    t0 = time.time()
    resp = client().chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or ""
    usage = resp.usage
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": model, "task": task, "content": content}, ensure_ascii=False), encoding="utf-8")
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": task, "model": model, "seconds": round(time.time() - t0, 1),
             "input_tokens": usage.prompt_tokens if usage else None, "output_tokens": usage.completion_tokens if usage else None}
    if usage and model in PRICES:
        pin, pout = PRICES[model]
        entry["usd"] = round(usage.prompt_tokens / 1e6 * pin + usage.completion_tokens / 1e6 * pout, 6)
    log_usage(entry)
    return content


def search(model: str, prompt: str, task: str) -> dict:
    """Ask a model with the web_search tool (Responses API). Returns {"text", "citations", "searches"}, cached like chat().

    The usage log records the number of web searches, which are billed per call on top of tokens.
    """
    key_material = json.dumps({"model": model, "input": prompt, "tools": ["web_search"]}, sort_keys=True)
    key = hashlib.sha256(key_material.encode()).hexdigest()
    path = CACHE / key[:2] / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["result"]
    t0 = time.time()
    resp = client().responses.create(model=model, tools=[{"type": "web_search"}], input=prompt)
    searches, citations = 0, []
    for item in resp.output:
        if item.type == "web_search_call":
            searches += 1
        elif item.type == "message":
            for part in item.content:
                citations += [a.url for a in getattr(part, "annotations", None) or [] if getattr(a, "url", None)]
    result = {"text": resp.output_text or "", "citations": list(dict.fromkeys(citations)), "searches": searches}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model": model, "task": task, "result": result}, ensure_ascii=False), encoding="utf-8")
    usage = resp.usage
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": task, "model": model, "seconds": round(time.time() - t0, 1),
             "input_tokens": usage.input_tokens if usage else None, "output_tokens": usage.output_tokens if usage else None,
             "web_searches": searches}
    if usage and model in PRICES:
        pin, pout = PRICES[model]
        entry["usd"] = round(usage.input_tokens / 1e6 * pin + usage.output_tokens / 1e6 * pout, 6)  # excludes the per-search fee
    log_usage(entry)
    return result


def chat_json(model: str, messages: list[dict], task: str, **options) -> dict:
    return json.loads(chat(model, messages, task, json_mode=True, **options))


def usage_summary() -> dict:
    """Token usage and (where prices are known) cost so far, per task and model."""
    totals: dict[str, dict] = {}
    if USAGE.exists():
        for line in USAGE.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            t = totals.setdefault(f"{e['task']} / {e['model']}", {"calls": 0, "input_tokens": 0, "output_tokens": 0, "usd": 0.0, "web_searches": 0})
            t["calls"] += 1
            t["web_searches"] += e.get("web_searches") or 0
            t["input_tokens"] += e.get("input_tokens") or 0
            t["output_tokens"] += e.get("output_tokens") or 0
            t["usd"] += e.get("usd") or 0.0
    return totals
