"""
Groq model setup, compatibility fixes and automatic model fallback.

Groq's free tier gives each model its own limits:
  - per minute (TPM/RPM): short waits, handled by retrying the same call
  - per day (TPD/RPD): the model is unusable until the daily reset

When a model hits its DAILY limit, calls switch automatically to the other
model, which has a separate quota. The switch is recorded so the app can show
a banner and the report can say which model produced it.

Limits belong to a Groq account, so the "out for today" state is tracked per
API key: the app owner's shared key, and any personal key a user adds when the
shared key is used up. Keys are never stored; only a short one-way hash is
kept as the lookup label.

Compatibility fixes (Groq is reached through CrewAI's LiteLLM path):
  - strips `cache_breakpoint` / `cache_control` from messages (Groq rejects them)
  - strips the internal `is_litellm` keyword
"""

import hashlib
import re
import threading
import time
from datetime import datetime, timezone

import litellm

HEAVY_MODEL = "groq/openai/gpt-oss-120b"   # specialists and critical reviewer
LIGHT_MODEL = "groq/openai/gpt-oss-20b"    # intake/routing and research synthesis
FALLBACK = {HEAVY_MODEL: LIGHT_MODEL, LIGHT_MODEL: HEAVY_MODEL}

_UNSUPPORTED_KWARGS = ["is_litellm"]
_UNSUPPORTED_MESSAGE_KEYS = ["cache_breakpoint", "cache_control"]
_MAX_SHORT_RETRIES = 8
_WAIT_RE = re.compile(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)", re.IGNORECASE)
_DAILY_RE = re.compile(r"per day|\(TPD\)|\(RPD\)", re.IGNORECASE)

_lock = threading.Lock()
_exhausted = {}          # (key_id, model) -> UTC date string when its daily limit was hit
_switch_events = []      # [{"time", "from", "to"}]
_patched = False


class AllModelsExhausted(Exception):
    """Both models reached their daily free limit."""


def short_name(model: str) -> str:
    return model.rsplit("/", 1)[-1]


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def key_id(api_key) -> str:
    return hashlib.sha256(str(api_key or "").encode()).hexdigest()[:12]


def is_exhausted(model: str, api_key=None, kid=None) -> bool:
    kid = kid or key_id(api_key)
    with _lock:
        return _exhausted.get((kid, model)) == _today()


def _mark_exhausted(model: str, api_key=None, kid=None):
    kid = kid or key_id(api_key)
    with _lock:
        _exhausted[(kid, model)] = _today()


def all_exhausted(api_key) -> bool:
    """True when both models are out for today on this key."""
    return all(is_exhausted(m, api_key) for m in (HEAVY_MODEL, LIGHT_MODEL))


def _record_switch(src: str, dst: str):
    with _lock:
        _switch_events.append({"time": datetime.now().strftime("%H:%M:%S"), "from": short_name(src), "to": short_name(dst)})


def switch_events_since(index: int):
    with _lock:
        return list(_switch_events[index:])


def switch_event_count() -> int:
    with _lock:
        return len(_switch_events)


def fallback_status(api_key):
    """Models currently over their daily limit on this key, for the banner."""
    return [short_name(m) for m in (HEAVY_MODEL, LIGHT_MODEL) if is_exhausted(m, api_key)]


def _wait_seconds(exc, attempt) -> float:
    m = _WAIT_RE.search(str(exc))
    if not m:
        return min(2.0 * (attempt + 1), 20.0)
    minutes, value, unit = m.groups()
    secs = float(value) / 1000.0 if unit.lower() == "ms" else float(value)
    return secs + (int(minutes) * 60 if minutes else 0)


def _clean(kwargs):
    for key in _UNSUPPORTED_KWARGS:
        kwargs.pop(key, None)
    for msg in kwargs.get("messages") or []:
        if isinstance(msg, dict):
            for key in _UNSUPPORTED_MESSAGE_KEYS:
                msg.pop(key, None)


def _pick_model(requested: str, kid: str) -> str:
    """Route straight to the fallback if the requested model is already out
    for today on this key; raise if both are out."""
    if requested not in FALLBACK or not is_exhausted(requested, kid=kid):
        return requested
    other = FALLBACK[requested]
    if is_exhausted(other, kid=kid):
        raise AllModelsExhausted("Both Groq models have reached today's free limit.")
    return other


def _guarded_call(call, args, kwargs):
    _clean(kwargs)
    kid = key_id(kwargs.get("api_key"))
    requested = kwargs.get("model", "")
    kwargs["model"] = _pick_model(requested, kid)
    if kwargs["model"] != requested:
        _record_switch(requested, kwargs["model"])
    attempt = 0
    while True:
        try:
            return call(*args, **kwargs)
        except litellm.RateLimitError as exc:
            model = kwargs.get("model", "")
            if _DAILY_RE.search(str(exc)) and model in FALLBACK:
                _mark_exhausted(model, kid=kid)
                other = FALLBACK[model]
                if is_exhausted(other, kid=kid):
                    raise AllModelsExhausted("Both Groq models have reached today's free limit.") from exc
                kwargs["model"] = other
                _record_switch(model, other)
                attempt = 0
                continue
            if attempt >= _MAX_SHORT_RETRIES:
                raise
            time.sleep(min(_wait_seconds(exc, attempt) + 0.5, 65.0))
            attempt += 1


def apply_llm_guard():
    """Patch litellm once per process. Safe to call on every rerun."""
    global _patched
    if _patched:
        return
    original_completion = litellm.completion
    original_acompletion = litellm.acompletion

    def completion(*args, **kwargs):
        return _guarded_call(original_completion, args, kwargs)

    async def acompletion(*args, **kwargs):
        _clean(kwargs)
        kwargs["model"] = _pick_model(kwargs.get("model", ""), key_id(kwargs.get("api_key")))
        return await original_acompletion(*args, **kwargs)

    litellm.drop_params = True  # drop any parameter Groq does not accept instead of failing
    litellm.completion = completion
    litellm.acompletion = acompletion
    _patched = True


def build_llms(api_key: str):
    """Heavy model for specialists/reviewer, light model for intake/research."""
    from crewai import LLM

    heavy = LLM(model=HEAVY_MODEL, api_key=api_key, temperature=0.3, max_tokens=4096)
    light = LLM(model=LIGHT_MODEL, api_key=api_key, temperature=0.2, max_tokens=3072,
                reasoning_effort="low")
    return heavy, light


def validate_key(api_key: str):
    """Quick check that a Groq key works, using the free model-list endpoint
    (no tokens used). Returns (ok, message)."""
    import requests

    key = (api_key or "").strip()
    if not key.startswith("gsk_") or len(key) < 20:
        return False, "That doesn't look like a Groq key. Groq keys start with gsk_."
    try:
        r = requests.get("https://api.groq.com/openai/v1/models",
                         headers={"Authorization": f"Bearer {key}"}, timeout=10)
    except requests.exceptions.RequestException:
        return True, "Couldn't reach Groq to check the key; it will be tried on your analysis."
    if r.status_code == 200:
        return True, ""
    if r.status_code in (401, 403):
        return False, "Groq rejected this key. Copy it again from console.groq.com/keys."
    return True, "Groq didn't confirm the key right now; it will be tried on your analysis."
