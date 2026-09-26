"""OpenRouter chat calls with cost and latency capture."""
import json
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache

from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from . import config


@dataclass
class LLMResult:
    text: str
    model: str            # model OpenRouter actually used (matters for openrouter/auto)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None
    raw_usage: dict = field(default_factory=dict)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config._req("OPENROUTER_API_KEY"),
        timeout=90,
    )


def chat(model: str, system: str, user: str, max_tokens: int = 1500, retries: int = 2) -> LLMResult:
    """One chat completion. Never raises for API errors: returns LLMResult with .error set."""
    last_err = None
    for attempt in range(retries + 1):
        t0 = time.perf_counter()
        try:
            resp = _client().chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0,
                max_tokens=max_tokens,
                extra_body={"usage": {"include": True}},
            )
            latency = int((time.perf_counter() - t0) * 1000)
            usage = resp.usage
            extra = (getattr(usage, "model_extra", None) or {}) if usage else {}
            return LLMResult(
                text=(resp.choices[0].message.content or "").strip(),
                model=resp.model or model,
                tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                tokens_out=getattr(usage, "completion_tokens", 0) or 0,
                cost_usd=float(extra.get("cost") or 0.0),
                latency_ms=latency,
                raw_usage=extra,
            )
        except (RateLimitError, APITimeoutError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1))
        except APIError as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt == retries:
                break
            time.sleep(1)
    return LLMResult(text="", model=model, error=last_err)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json_text(text: str) -> str:
    """Pull a JSON object/array out of a model reply (handles ``` fences and chatter)."""
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    text = text.strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("no JSON found in model output")
    start = min(starts)
    closer = "}" if text[start] == "{" else "]"
    end = text.rfind(closer)
    if end <= start:
        raise ValueError("unterminated JSON in model output")
    candidate = text[start:end + 1]
    json.loads(candidate)  # validate plain JSON syntax (Extended JSON is still valid JSON)
    return candidate
