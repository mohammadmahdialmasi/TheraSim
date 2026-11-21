"""Run a small synthetic bilingual TheraSim benchmark against local Ollama."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"

CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "english_persona",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a fictional client in a psychotherapy-skills "
                    "training simulation. Stay consistent with this invented "
                    "persona: a 29-year-old office worker who avoids asking "
                    "colleagues for help because they fear seeming incompetent. "
                    "Speak naturally and briefly; do not give clinical advice."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I had another difficult week. What would it be like for "
                    "you to ask a colleague for help?"
                ),
            },
        ],
    },
    {
        "id": "persian_persona",
        "messages": [
            {
                "role": "system",
                "content": (
                    "در یک شبیه‌سازی آموزشی، نقش یک مراجع کاملاً خیالی را بازی "
                    "کن. شخصیت: کارمند ۲۹ ساله‌ای که از درخواست کمک از "
                    "همکاران دوری می‌کند چون می‌ترسد ناتوان به نظر برسد. "
                    "کوتاه و طبیعی پاسخ بده و توصیهٔ درمانی نده."
                ),
            },
            {
                "role": "user",
                "content": (
                    "این هفته هم سخت گذشت. اگر از همکارت کمک بخواهی، چه "
                    "احساسی خواهی داشت؟"
                ),
            },
        ],
    },
    {
        "id": "english_context_retention",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a fictional client for a training simulation. "
                    "Persona: a fictional 29-year-old office worker who fears "
                    "asking colleagues for help because they may seem "
                    "incompetent. Reply briefly in character."
                ),
            },
            {"role": "user", "content": "I struggle to ask my team for help."},
            {
                "role": "assistant",
                "content": "I worry they will think I am incompetent.",
            },
            {
                "role": "user",
                "content": "What did you say you were afraid they would think?",
            },
        ],
    },
    {
        "id": "structured_output",
        "format": "json",
        "messages": [
            {
                "role": "system",
                "content": (
                    'Return one JSON object with exactly the keys "response" '
                    'and "persona_consistent". "response" must be a short '
                    "utterance from a fictional person afraid to ask "
                    "colleagues for help; persona_consistent must be a boolean."
                ),
            },
            {
                "role": "user",
                "content": (
                    "I wonder what holds you back from asking a colleague "
                    "for help."
                ),
            },
        ],
    },
)


def run_case(model: str, case: dict[str, Any], timeout: float) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": case["messages"],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": 192},
    }
    if "format" in case:
        payload["format"] = case["format"]

    request = Request(
        OLLAMA_CHAT_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"{case['id']} failed to reach local Ollama: {exc}"
        ) from exc
    elapsed = time.perf_counter() - started

    message = result.get("message")
    if not isinstance(message, dict):
        raise RuntimeError(f"{case['id']} returned no chat message.")
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(
            f"{case['id']} returned no visible content; retry with a "
            "supported Ollama model and inspect its thinking settings."
        )

    structured_valid: bool | None = None
    if case.get("format") == "json":
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError:
            structured_valid = False
        else:
            structured_valid = (
                isinstance(decoded, dict)
                and set(decoded) == {"response", "persona_consistent"}
                and isinstance(decoded["response"], str)
                and isinstance(decoded["persona_consistent"], bool)
            )

    return {
        "case": case["id"],
        "seconds": round(elapsed, 3),
        "prompt_tokens": result.get("prompt_eval_count"),
        "generated_tokens": result.get("eval_count"),
        "structured_output_valid": structured_valid,
        "response": content,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gemma-4-E2B:latest")
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    if not args.model.strip() or not 1 <= args.timeout <= 600:
        parser.error("model must be non-empty and timeout must be 1..600 seconds")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    results = [run_case(args.model, case, args.timeout) for case in CASES]
    print(
        json.dumps(
            {
                "endpoint": OLLAMA_CHAT_URL,
                "model": args.model,
                "results": results,
                "note": (
                    "Review generated responses manually. This synthetic "
                    "smoke benchmark is not clinical or psychometric validation."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
