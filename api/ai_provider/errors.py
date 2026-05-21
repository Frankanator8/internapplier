import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

_KEY_INFO_URL = "https://openrouter.ai/api/v1/auth/key"
_KEY_INFO_TIMEOUT = 3.0

_STATUS_MESSAGES = {
    400: "Bad request sent to the AI provider",
    401: "OpenRouter API key is missing or invalid. Check your settings.",
    402: "Insufficient OpenRouter credits. Add credits at https://openrouter.ai/credits.",
    403: "Input was flagged by content moderation.",
    408: "AI provider timed out. Try again.",
    429: "Rate limit exceeded.",
    502: "Selected model is currently unavailable. Try a different model.",
    503: "No available provider for this model right now. Try again shortly.",
}


class ProviderError(Exception):
    """User-facing provider error. str(exc) is safe to show in UI."""


def _extract_error_body(response: requests.Response) -> tuple[str | None, dict]:
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        return None, {}
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        return None, {}
    msg = err.get("message")
    meta = err.get("metadata") if isinstance(err.get("metadata"), dict) else {}
    return (msg if isinstance(msg, str) else None), meta


def _fetch_key_info(api_key: str | None) -> dict | None:
    if not api_key:
        return None
    try:
        r = requests.get(
            _KEY_INFO_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=_KEY_INFO_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json().get("data")
        return data if isinstance(data, dict) else None
    except Exception:
        logger.debug("provider-error: /auth/key lookup failed", exc_info=True)
        return None


def _seconds_until_reset(response: requests.Response) -> float | None:
    raw = response.headers.get("X-RateLimit-Reset") or response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    # X-RateLimit-Reset is epoch milliseconds per OpenRouter docs; Retry-After is seconds.
    if val > 1e12:
        seconds = val / 1000.0 - time.time()
    elif val > 1e9:
        seconds = val - time.time()
    else:
        seconds = val
    return max(0.0, seconds)


def _format_rate_limit_suffix(
    response: requests.Response | None, key_info: dict | None
) -> str:
    parts: list[str] = []
    if key_info:
        rl = key_info.get("rate_limit")
        if isinstance(rl, dict):
            req = rl.get("requests")
            interval = rl.get("interval")
            if req and interval:
                parts.append(f"Rate limit: {req} req / {interval}.")
    if response is not None:
        secs = _seconds_until_reset(response)
        if secs is not None:
            parts.append(f"Try again in ~{int(secs)}s.")
    if key_info:
        remaining = key_info.get("limit_remaining")
        limit = key_info.get("limit")
        if isinstance(remaining, (int, float)) and isinstance(limit, (int, float)):
            parts.append(f"Credits remaining: ${remaining:.2f} of ${limit:.2f}.")
        elif isinstance(remaining, (int, float)):
            parts.append(f"Credits remaining: ${remaining:.2f}.")
    return (" " + " ".join(parts)) if parts else ""


def _from_http_error(exc: requests.exceptions.HTTPError, api_key: str | None) -> ProviderError:
    response = exc.response
    if response is None:
        return ProviderError(f"AI provider HTTP error: {exc}")

    status = response.status_code
    upstream_msg, meta = _extract_error_body(response)
    base = _STATUS_MESSAGES.get(status)

    if status == 400 and upstream_msg:
        message = f"{base} — {upstream_msg}."
    elif status == 403:
        reason = meta.get("reasons") or meta.get("reason") or upstream_msg
        message = f"{base}" + (f" Reason: {reason}." if reason else "")
    elif status in (429, 402):
        key_info = _fetch_key_info(api_key)
        message = (base or f"HTTP {status}.") + _format_rate_limit_suffix(response, key_info)
    elif base:
        message = base
    else:
        message = f"AI provider returned HTTP {status}" + (f": {upstream_msg}" if upstream_msg else ".")

    return ProviderError(message)


def parse_provider_error(
    exc: BaseException, *, api_key: str | None = None
) -> ProviderError:
    """Translate a raw exception from an OpenRouter call into a user-facing ProviderError.

    For 429/402 responses, queries OpenRouter's /auth/key endpoint to append the
    user's current rate-limit window, time-until-reset, and credits remaining.
    """
    if isinstance(exc, ProviderError):
        return exc

    if isinstance(exc, requests.exceptions.HTTPError):
        return _from_http_error(exc, api_key)

    if isinstance(exc, requests.exceptions.Timeout):
        return ProviderError("AI provider timed out. Check your connection and try again.")

    if isinstance(exc, requests.exceptions.ConnectionError):
        return ProviderError("Couldn't reach the AI provider. Check your network connection.")

    if isinstance(exc, (json.JSONDecodeError, ValueError)):
        return ProviderError("AI returned unexpected format — please try again.")

    return ProviderError(f"Unexpected provider error: {type(exc).__name__}: {exc}")
