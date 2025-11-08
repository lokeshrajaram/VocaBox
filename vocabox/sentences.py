import ast
import json
import os
import re
import urllib.request
from typing import Any, Dict, List, Sequence


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


def _loads_lenient(text: str):
    if not text:
        return None
    base = text.strip()
    variants = [base]
    if base.startswith("<") and base.endswith(">"):
        variants.append(base[1:-1].strip())
    for opener, closer in (("[", "]"), ("{", "}")):
        start = base.find(opener)
        end = base.rfind(closer)
        if start != -1 and end != -1 and end > start:
            variants.append(base[start:end + 1])
    seen = set()
    for candidate in variants:
        cand = candidate.strip()
        if not cand or cand in seen:
            continue
        seen.add(cand)
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(cand)
            except Exception:
                continue
    return None


def _candidate_strings_from(entry: Any) -> List[str]:
    """
    Normalize any entry (dict/str/etc.) into a list of possible sentence strings.
    """
    candidates: List[str] = []
    if entry is None:
        return candidates
    if isinstance(entry, dict):
        for key in ("sentence", "example", "definition", "text", "value", "content", "message", "output", "result", "response", "answer", "word"):
            val = entry.get(key)
            if isinstance(val, str):
                candidates.append(_normalize_sentence(val))
    elif isinstance(entry, (list, tuple)):
        for item in entry:
            candidates.extend(_candidate_strings_from(item))
    else:
        text = _normalize_sentence(entry)
        # Try to parse dict-like strings (e.g., "{'word': '...'}")
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, dict):
                    candidates.extend(_candidate_strings_from(parsed))
                    return candidates
            except Exception:
                pass
        candidates.append(text)
    return [c for c in candidates if c]


def _sanitize_sentences(raw: Sequence[Any], items: Sequence[Dict[str, str]]) -> List[str]:
    candidates: List[str] = []
    for entry in raw or []:
        candidates.extend(_candidate_strings_from(entry))
    candidates = [c for c in candidates if c]
    if not candidates:
        return []
    all_candidates = candidates.copy()
    sentences: List[str] = []
    remaining = candidates.copy()
    for idx, item in enumerate(items):
        word = (item.get("word") or "").strip()
        definition = (item.get("definition") or "").strip()
        chosen = None
        if word:
            word_lower = word.lower()
            for idx, candidate in enumerate(remaining):
                if len(candidate.split()) >= 3 and word_lower in candidate.lower():
                    chosen = remaining.pop(idx)
                    break
        if not chosen:
            while remaining:
                candidate = remaining.pop(0)
                if len(candidate.split()) >= 3:
                    chosen = candidate
                    break
        if not chosen and all_candidates:
            chosen = all_candidates[idx % len(all_candidates)]
        if not chosen:
            return []
        sentences.append(_normalize_sentence(chosen))
    return sentences


_VALUE_RE = re.compile(r"'(sentence|example|definition|text|value|content|message|output|result|response|answer|word)':\s*(\"|\')(.*?)\2", re.IGNORECASE | re.DOTALL)


def _normalize_sentence(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def _extract_sentences_from_text(text: str) -> List[str]:
    sentences: List[str] = []
    if not text:
        return sentences
    for _, _, value in _VALUE_RE.findall(text):
        cleaned = _normalize_sentence(
            value.replace("\\'", "'")
            .replace('\\"', '"')
            .replace("\\n", " ")
        )
        if len(cleaned.split()) >= 3:
            sentences.append(cleaned)
    return sentences


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
        model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        if not model:
            return []
        prompt = {
            "role": "system",
            "content": (
                "You help middle school students learn vocabulary by writing one sentence "
                "per word. Each sentence must be positive, age-appropriate, and clearly show the word's meaning. "
                "Return a JSON array of plain strings (each entry is just the example sentence)."
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
        stripped = _strip_code_fence(content)
        parsed = _loads_lenient(stripped)
        if isinstance(parsed, dict) and "sentences" in parsed:
            parsed = parsed["sentences"]
        if isinstance(parsed, str):
            parsed = _loads_lenient(parsed)
            if isinstance(parsed, dict) and "sentences" in parsed:
                parsed = parsed["sentences"]
        if isinstance(parsed, (list, tuple)):
            cleaned = _sanitize_sentences(parsed, items)
            if len(cleaned) == len(items):
                return cleaned
        text_candidates = _extract_sentences_from_text(stripped)
        if text_candidates:
            cleaned = _sanitize_sentences(text_candidates, items)
            if len(cleaned) == len(items):
                return cleaned
    except Exception as exc:
        print("Sentence generation via Ollama failed:", exc)
    return []


__all__ = ["generate_sentences_via_ollama"]
