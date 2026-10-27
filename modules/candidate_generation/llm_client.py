"""Google Gemini client — the only place in OASIS that calls an LLM.

Deliberately small and dependency-light (httpx only, which the backend
already ships). One HTTP call per generation, JSON-mode responses, and
explicit error types so the API layer can return a useful status code
instead of a stack trace.

Configuration (environment variables, or ``OASIS/.env``):

    GEMINI_API_KEY  (or GOOGLE_API_KEY)     required
    GEMINI_MODEL                            default "gemini-3.8-flash"
    GEMINI_API_BASE                         default Google Generative Language API
    GEMINI_TIMEOUT_SECONDS                  default 120
    GEMINI_MAX_OUTPUT_TOKENS                default 8192

Security: the key is read from the environment and is never logged,
serialised into a response, or included in raised error messages.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from modules.config import get_env, get_env_float, get_env_first, get_env_int

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

_FENCE_RE = re.compile(r"```(?:json|python|[\w+-]*)?\s*(.*?)```", re.DOTALL)


class LLMError(RuntimeError):
    """Base class for LLM failures."""


class LLMNotConfigured(LLMError):
    """No API key is available, so generation cannot run."""


class LLMRequestError(LLMError):
    """The provider rejected the request or returned an unusable payload."""


def _strip_code_fences(text: str) -> str:
    """Remove markdown fences an LLM may add despite instructions."""
    text = text.strip()
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def _first_json_object(text: str) -> str:
    """Extract the first balanced ``{...}`` block from surrounding prose."""
    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return text[start:]


class GeminiClient:
    """Minimal synchronous client for the Gemini ``generateContent`` API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key or get_env_first(["GEMINI_API_KEY", "GOOGLE_API_KEY"])
        self.model = model or get_env("GEMINI_MODEL", DEFAULT_MODEL)
        self.api_base = (api_base or get_env("GEMINI_API_BASE", DEFAULT_API_BASE)).rstrip("/")
        self.timeout = timeout or get_env_float("GEMINI_TIMEOUT_SECONDS", 120.0)
        self.max_output_tokens = get_env_int("GEMINI_MAX_OUTPUT_TOKENS", 8192)

    # ------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def status(self) -> dict[str, Any]:
        """Connection info safe to return to a client (never the key)."""
        return {
            "provider": "google-gemini",
            "configured": self.is_configured,
            "model": self.model,
            "api_base": self.api_base,
            "timeout_seconds": self.timeout,
            "hint": (
                None
                if self.is_configured
                else "Set GEMINI_API_KEY in OASIS/.env to enable candidate generation."
            ),
        }

    # ------------------------------------------------------------
    # GENERATION
    # ------------------------------------------------------------

    def _build_payload(
        self,
        prompt: str,
        system_instruction: str | None,
        temperature: float,
        max_output_tokens: int,
        json_mode: bool,
    ) -> dict[str, Any]:
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        return payload

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured:
            raise LLMNotConfigured(
                "No Gemini API key configured. Set GEMINI_API_KEY in OASIS/.env."
            )

        url = f"{self.api_base}/models/{self.model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key or "",
        }

        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except httpx.TimeoutException as exc:
            raise LLMRequestError(
                f"Gemini request timed out after {self.timeout:.0f}s."
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"Could not reach Gemini: {exc}") from exc

        if response.status_code >= 400:
            # The provider message is useful; the request headers (and key) are not.
            detail = _provider_error_message(response)
            raise LLMRequestError(
                f"Gemini returned HTTP {response.status_code}: {detail}"
            )

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise LLMRequestError("Gemini returned a non-JSON response.") from exc

    def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate plain text."""
        payload = self._build_payload(
            prompt,
            system_instruction,
            temperature,
            max_output_tokens or self.max_output_tokens,
            json_mode=False,
        )
        return self._extract_text(self._post(payload))

    def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Generate a JSON object.

        Uses the provider's JSON mode, then falls back to extracting the
        first balanced object when a model still wraps the payload in prose.
        """
        payload = self._build_payload(
            prompt,
            system_instruction,
            temperature,
            max_output_tokens or self.max_output_tokens,
            json_mode=True,
        )
        text = self._extract_text(self._post(payload))

        for candidate_text in (_strip_code_fences(text), _first_json_object(text)):
            try:
                parsed = json.loads(candidate_text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

        raise LLMRequestError(
            "Gemini did not return a JSON object. First 200 characters: "
            f"{text[:200]!r}"
        )

    def list_models(self) -> list[str]:
        """List models the configured key can use (diagnostics only)."""
        if not self.is_configured:
            raise LLMNotConfigured("No Gemini API key configured.")

        url = f"{self.api_base}/models"
        try:
            response = httpx.get(
                url,
                headers={"x-goog-api-key": self.api_key or ""},
                timeout=min(self.timeout, 30.0),
            )
        except httpx.HTTPError as exc:
            raise LLMRequestError(f"Could not reach Gemini: {exc}") from exc

        if response.status_code >= 400:
            raise LLMRequestError(
                f"Gemini returned HTTP {response.status_code}: "
                f"{_provider_error_message(response)}"
            )

        payload = response.json()
        names: list[str] = []
        for model in payload.get("models", []):
            name = str(model.get("name", ""))
            names.append(name.split("/", 1)[-1] if name else "")
        return [name for name in names if name]

    # ------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        """Pull the generated text out of a generateContent response."""
        prompt_feedback = payload.get("promptFeedback") or {}
        block_reason = prompt_feedback.get("blockReason")
        if block_reason:
            raise LLMRequestError(f"Gemini blocked the prompt ({block_reason}).")

        candidates = payload.get("candidates") or []
        if not candidates:
            raise LLMRequestError("Gemini returned no candidates.")

        first = candidates[0]
        finish_reason = first.get("finishReason")
        if finish_reason in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"}:
            raise LLMRequestError(f"Gemini refused to answer ({finish_reason}).")

        parts = (first.get("content") or {}).get("parts") or []
        text = "".join(str(part.get("text", "")) for part in parts).strip()

        if not text:
            raise LLMRequestError(
                f"Gemini returned an empty response (finishReason={finish_reason})."
            )

        if finish_reason == "MAX_TOKENS":
            raise LLMRequestError(
                "Gemini stopped at the output token limit; the code was truncated. "
                "Increase GEMINI_MAX_OUTPUT_TOKENS."
            )

        return text


def _provider_error_message(response: httpx.Response) -> str:
    """Best-effort human-readable message from a provider error body."""
    try:
        body = response.json()
    except Exception:
        return response.text[:300] or "no details"

    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        message = str(error.get("message", "")).strip()
        status = str(error.get("status", "")).strip()
        if message and status:
            return f"{message} ({status})"
        if message:
            return message
    return str(body)[:300]
