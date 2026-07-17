"""
Multi-provider AI abstraction for Siraj.

Provider chain: Gemini (primary) → OpenAI (secondary) → Arabic fallback message.
Includes exponential backoff with jitter, structured logging, and error classification.
"""

import time
import random
import asyncio
import logging
import json
from dataclasses import dataclass, field
from typing import Optional, Any, AsyncGenerator
from enum import Enum

from google import genai
from google.genai import types as genai_types

from backend.app.config import settings

logger = logging.getLogger("siraj.ai.provider")


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class ProviderName(str, Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    FALLBACK = "fallback"


class ErrorCategory(str, Enum):
    RATE_LIMIT = "rate_limit"       # HTTP 429
    TIMEOUT = "timeout"             # Request timeout
    SERVICE_DOWN = "service_down"   # HTTP 503
    AUTH_ERROR = "auth_error"       # HTTP 401/403
    MODEL_NOT_FOUND = "model_not_found"  # HTTP 404
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class ProviderResponse:
    """Wrapper around a provider response with metadata."""
    response: Any = None
    provider: ProviderName = ProviderName.FALLBACK
    latency_ms: float = 0.0
    retries: int = 0
    is_fallback: bool = False
    fallback_message: str = ""
    error: Optional[str] = None


# Arabic fallback message when all providers fail
FALLBACK_MESSAGE_AR = (
    "عذراً، خدمة المساعد الذكي غير متوفرة مؤقتاً بسبب ضغط على الخوادم. "
    "يرجى المحاولة مرة أخرى بعد لحظات. "
    "بياناتك المالية آمنة ويمكنك تصفح لوحة التحكم بشكل طبيعي."
)


# ---------------------------------------------------------------------------
# Error Classification
# ---------------------------------------------------------------------------

def _classify_error(exc: Exception) -> ErrorCategory:
    """Classify an exception into a retryable/non-retryable category."""
    error_str = str(exc).lower()

    # Google GenAI errors
    if "429" in error_str or "resource_exhausted" in error_str or "rate" in error_str:
        return ErrorCategory.RATE_LIMIT
    if "503" in error_str or "unavailable" in error_str:
        return ErrorCategory.SERVICE_DOWN
    if "401" in error_str or "403" in error_str or "permission" in error_str or "unauthenticated" in error_str:
        return ErrorCategory.AUTH_ERROR
    if "404" in error_str or "not_found" in error_str or "no longer available" in error_str:
        return ErrorCategory.MODEL_NOT_FOUND
    if "timeout" in error_str or "timed out" in error_str:
        return ErrorCategory.TIMEOUT
    if "connection" in error_str or "network" in error_str or "dns" in error_str:
        return ErrorCategory.NETWORK_ERROR

    # OpenAI errors (if available)
    try:
        import openai
        if isinstance(exc, openai.RateLimitError):
            return ErrorCategory.RATE_LIMIT
        if isinstance(exc, openai.APITimeoutError):
            return ErrorCategory.TIMEOUT
        if isinstance(exc, openai.AuthenticationError):
            return ErrorCategory.AUTH_ERROR
        if isinstance(exc, openai.NotFoundError):
            return ErrorCategory.MODEL_NOT_FOUND
        if isinstance(exc, openai.APIConnectionError):
            return ErrorCategory.NETWORK_ERROR
        if isinstance(exc, openai.InternalServerError):
            return ErrorCategory.SERVICE_DOWN
    except ImportError:
        pass

    return ErrorCategory.UNKNOWN


def _is_retryable(category: ErrorCategory) -> bool:
    """Determine if an error category warrants a retry."""
    return category in {
        ErrorCategory.RATE_LIMIT,
        ErrorCategory.TIMEOUT,
        ErrorCategory.SERVICE_DOWN,
        ErrorCategory.NETWORK_ERROR,
    }


# ---------------------------------------------------------------------------
# Backoff Helper
# ---------------------------------------------------------------------------

async def _backoff_delay(attempt: int, base_delay: float = 1.0) -> float:
    """
    Exponential backoff with jitter.
    attempt 0 → ~1s, attempt 1 → ~2s, attempt 2 → ~4s, capped at 16s.
    """
    delay = min(base_delay * (2 ** attempt), 16.0)
    jitter = random.uniform(-0.5, 0.5)
    actual_delay = max(0.1, delay + jitter)
    logger.info("Backoff: waiting %.2fs (attempt=%d, base=%.1fs)", actual_delay, attempt + 1, base_delay)
    await asyncio.sleep(actual_delay)
    return actual_delay


# ---------------------------------------------------------------------------
# Gemini Provider
# ---------------------------------------------------------------------------

def _get_gemini_client() -> genai.Client:
    """Create a Gemini client from settings."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _call_gemini_sync(
    client: genai.Client,
    model: str,
    contents: list,
    config: Any,
) -> Any:
    """Synchronous Gemini generate_content call."""
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


async def _call_gemini(
    contents: list,
    config: Any,
    model: str,
) -> Any:
    """Call Gemini API with timeout protection."""
    client = _get_gemini_client()
    loop = asyncio.get_event_loop()
    response = await asyncio.wait_for(
        loop.run_in_executor(None, _call_gemini_sync, client, model, contents, config),
        timeout=settings.AI_REQUEST_TIMEOUT,
    )
    return response


def _stream_gemini_sync(
    client: genai.Client,
    model: str,
    contents: list,
    config: Any,
):
    """Synchronous Gemini streaming generator."""
    return client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=config,
    )


# ---------------------------------------------------------------------------
# OpenAI Provider
# ---------------------------------------------------------------------------

def _openai_available() -> bool:
    """Check if OpenAI is configured and importable."""
    if not settings.OPENAI_API_KEY:
        return False
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        logger.warning("OPENAI_API_KEY is set but 'openai' package is not installed")
        return False


def _convert_contents_for_openai(
    contents: list,
    system_prompt: str,
    tools: list,
) -> tuple[list[dict], list[dict]]:
    """
    Convert Gemini-format contents and tools to OpenAI chat format.
    Returns (messages, tools_openai).
    """
    messages = []

    # System message
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # Convert content history
    for content in contents:
        role = getattr(content, "role", "user")
        parts = getattr(content, "parts", [])

        if role == "user":
            text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]
            if text_parts:
                messages.append({"role": "user", "content": "\n".join(text_parts)})

        elif role == "model":
            # Check for function calls
            func_calls = []
            text_parts = []
            for p in parts:
                if hasattr(p, "function_call") and p.function_call:
                    fc = p.function_call
                    func_calls.append({
                        "id": f"call_{fc.name}_{len(func_calls)}",
                        "type": "function",
                        "function": {
                            "name": fc.name,
                            "arguments": json.dumps(fc.args, ensure_ascii=False) if fc.args else "{}",
                        },
                    })
                elif hasattr(p, "text") and p.text:
                    text_parts.append(p.text)

            if func_calls:
                msg = {"role": "assistant", "tool_calls": func_calls}
                if text_parts:
                    msg["content"] = "\n".join(text_parts)
                messages.append(msg)
            elif text_parts:
                messages.append({"role": "assistant", "content": "\n".join(text_parts)})

        elif role == "tool":
            for p in parts:
                if hasattr(p, "function_response") and p.function_response:
                    fr = p.function_response
                    # Find matching call ID
                    call_id = f"call_{fr.name}_0"
                    for prev_msg in reversed(messages):
                        if prev_msg.get("role") == "assistant" and prev_msg.get("tool_calls"):
                            for tc in prev_msg["tool_calls"]:
                                if tc["function"]["name"] == fr.name:
                                    call_id = tc["id"]
                                    break
                            break
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(fr.response, ensure_ascii=False) if fr.response else "{}",
                    })

    # Convert tools to OpenAI format
    tools_openai = []
    for tool_func in tools:
        # Extract function metadata from the callable
        doc = tool_func.__doc__ or ""
        # Build a minimal tool definition
        import inspect
        sig = inspect.signature(tool_func)
        properties = {}
        required = []
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == float:
                    param_type = "number"
                elif param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"
            properties[param_name] = {"type": param_type, "description": param_name}
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        tools_openai.append({
            "type": "function",
            "function": {
                "name": tool_func.__name__,
                "description": doc.strip()[:500],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })

    return messages, tools_openai


@dataclass
class OpenAIFunctionCall:
    """Mimics Gemini's function call structure for unified handling."""
    name: str
    args: dict


@dataclass
class OpenAIResponseWrapper:
    """Wraps OpenAI response to match Gemini response interface."""
    text: Optional[str] = None
    function_calls: Optional[list] = None

    @classmethod
    def from_openai_response(cls, response) -> "OpenAIResponseWrapper":
        """Convert an OpenAI ChatCompletion response to our wrapper."""
        choice = response.choices[0]
        message = choice.message

        func_calls = None
        if message.tool_calls:
            func_calls = []
            for tc in message.tool_calls:
                args = {}
                if tc.function.arguments:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                func_calls.append(OpenAIFunctionCall(
                    name=tc.function.name,
                    args=args,
                ))

        return cls(
            text=message.content,
            function_calls=func_calls,
        )


async def _call_openai(
    contents: list,
    system_prompt: str,
    tools: list,
    model: str,
) -> OpenAIResponseWrapper:
    """Call OpenAI API (or Replit AI proxy) as secondary provider."""
    import openai

    kwargs = dict(
        api_key=settings.OPENAI_API_KEY,
        timeout=settings.AI_REQUEST_TIMEOUT,
    )
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL

    client = openai.AsyncOpenAI(**kwargs)

    messages, tools_openai = _convert_contents_for_openai(contents, system_prompt, tools)

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    if tools_openai:
        kwargs["tools"] = tools_openai

    response = await client.chat.completions.create(**kwargs)
    return OpenAIResponseWrapper.from_openai_response(response)


# ---------------------------------------------------------------------------
# Main Provider Class
# ---------------------------------------------------------------------------

class AIProvider:
    """
    Multi-provider AI abstraction for Siraj.
    
    Tries providers in order: Gemini → OpenAI → Arabic fallback.
    Each provider gets up to AI_RETRY_MAX attempts with exponential backoff
    for retryable errors. Non-retryable errors skip immediately to next provider.
    
    The fallback NEVER executes tool calls — it only returns a friendly message.
    """

    def __init__(self):
        self._max_retries = settings.AI_RETRY_MAX
        self._base_delay = settings.AI_RETRY_BASE_DELAY

    async def generate_content(
        self,
        contents: list,
        config: Any,
        system_prompt: str = "",
        tools: list = None,
    ) -> ProviderResponse:
        """
        Generate content through the provider chain.
        
        Returns a ProviderResponse with the response object and metadata.
        On total failure, returns a fallback response with is_fallback=True.
        """
        tools = tools or []

        # --- Try Gemini (Primary) ---
        if settings.GEMINI_API_KEY:
            result = await self._try_provider(
                provider_name=ProviderName.GEMINI,
                call_fn=lambda: _call_gemini(contents, config, settings.AI_PRIMARY_MODEL),
                max_retries=self._max_retries,
            )
            if result.response is not None:
                return result

        # --- Try OpenAI (Secondary) ---
        if _openai_available() and settings.AI_SECONDARY_MODEL:
            result = await self._try_provider(
                provider_name=ProviderName.OPENAI,
                call_fn=lambda: _call_openai(
                    contents, system_prompt, tools, settings.AI_SECONDARY_MODEL
                ),
                max_retries=max(1, self._max_retries - 1),  # Fewer retries for secondary
            )
            if result.response is not None:
                return result

        # --- Fallback: Arabic apology ---
        logger.critical(
            "ALL_PROVIDERS_FAILED | action=fallback | message=Returning Arabic apology"
        )
        return ProviderResponse(
            provider=ProviderName.FALLBACK,
            is_fallback=True,
            fallback_message=FALLBACK_MESSAGE_AR,
        )

    async def generate_content_stream(
        self,
        contents: list,
        config: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream text content from the primary provider (Gemini).
        
        Falls back to a single-chunk Arabic message if streaming fails.
        OpenAI streaming is not implemented to keep hackathon scope manageable.
        """
        start_time = time.time()

        # Try Gemini streaming with retries
        for attempt in range(self._max_retries):
            try:
                client = _get_gemini_client()
                response_stream = client.models.generate_content_stream(
                    model=settings.AI_PRIMARY_MODEL,
                    contents=contents,
                    config=config,
                )

                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    "STREAM_START | provider=gemini | model=%s | latency_ms=%.0f | attempt=%d",
                    settings.AI_PRIMARY_MODEL, latency_ms, attempt + 1,
                )

                for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text

                return  # Success — exit generator

            except Exception as exc:
                category = _classify_error(exc)
                logger.warning(
                    "STREAM_ERROR | provider=gemini | attempt=%d/%d | error_category=%s | error=%s",
                    attempt + 1, self._max_retries, category.value, str(exc)[:200],
                )
                if _is_retryable(category) and attempt < self._max_retries - 1:
                    await _backoff_delay(attempt, self._base_delay)
                    continue
                break

        # Streaming failed — yield fallback
        logger.critical("STREAM_ALL_FAILED | action=fallback")
        yield FALLBACK_MESSAGE_AR

    async def _try_provider(
        self,
        provider_name: ProviderName,
        call_fn,
        max_retries: int,
    ) -> ProviderResponse:
        """
        Try a single provider with retries and backoff.
        
        Returns ProviderResponse with response set on success,
        or response=None on exhausted retries.
        """
        total_retries = 0

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                response = await call_fn()
                latency_ms = (time.time() - start_time) * 1000

                logger.info(
                    "API_SUCCESS | provider=%s | model=%s | latency_ms=%.0f | retries=%d",
                    provider_name.value,
                    settings.AI_PRIMARY_MODEL if provider_name == ProviderName.GEMINI else settings.AI_SECONDARY_MODEL,
                    latency_ms,
                    total_retries,
                )

                return ProviderResponse(
                    response=response,
                    provider=provider_name,
                    latency_ms=latency_ms,
                    retries=total_retries,
                )

            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000
                category = _classify_error(exc)
                total_retries += 1

                logger.warning(
                    "API_ERROR | provider=%s | attempt=%d/%d | error_category=%s | "
                    "latency_ms=%.0f | error=%s",
                    provider_name.value,
                    attempt + 1,
                    max_retries,
                    category.value,
                    latency_ms,
                    str(exc)[:300],
                )

                # Non-retryable errors: skip to next provider immediately
                if not _is_retryable(category):
                    logger.error(
                        "NON_RETRYABLE | provider=%s | error_category=%s | skipping_to_next",
                        provider_name.value, category.value,
                    )
                    return ProviderResponse(
                        provider=provider_name,
                        retries=total_retries,
                        error=f"{category.value}: {str(exc)[:200]}",
                    )

                # Retryable: backoff and try again
                if attempt < max_retries - 1:
                    await _backoff_delay(attempt, self._base_delay)

        # All retries exhausted
        logger.error(
            "RETRIES_EXHAUSTED | provider=%s | total_retries=%d",
            provider_name.value, total_retries,
        )
        return ProviderResponse(
            provider=provider_name,
            retries=total_retries,
            error="retries_exhausted",
        )
