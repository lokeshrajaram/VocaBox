import json
import os
import urllib.request
from typing import Any, Dict, List


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        if len(parts) >= 2:
            inner = parts[1].strip()
            if inner.lower().startswith("json"):
                inner = inner[4:].lstrip()
            return inner
    return stripped


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset("utf-8") if resp.headers else "utf-8"
        text = resp.read().decode(charset or "utf-8")
    return json.loads(text or "{}")


def generate_sentences_via_ollama(items: List[Dict[str, str]]) -> List[str]:
    if not items:
        return []
    try:
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        if not model:
            return []
        prompt = {
            "role": "system",
            "content": (
                "You help middle school students learn vocabulary by writing one sentence "
                "per word. Each sentence must be positive, age-appropriate, and clearly "
                "demonstrate the word's meaning using the supplied definition. Return a JSON array of sentences."
            ),
        }
        user_message = {
            "role": "user",
            "content": json.dumps(
                [
                    {
                        "word": item.get("word", ""),
                        "definition": item.get("definition", ""),
                    }
                    for item in items
                ],
                ensure_ascii=False,
            ),
        }
        payload = {
            "model": model,
            "messages": [prompt, user_message],
            "stream": False,
            "options": {"temperature": 0.7},
        }
        data = _post_json(f"{base_url}/api/chat", payload, timeout=60)
        content = data.get("message", {}).get("content", "")
        sentences = json.loads(_strip_code_fence(content))
        if isinstance(sentences, list):
            cleaned = []
            for sentence in sentences:
                text = str(sentence).strip()
                cleaned.append(text)
            return cleaned
    except Exception as exc:
        print("Sentence generation via Ollama failed:", exc)
    return []


__all__ = ["generate_sentences_via_ollama"]
