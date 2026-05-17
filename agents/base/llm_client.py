"""
LangChain-based LLM wrapper used by every agent tier.

Stack:
  - langchain-openai ChatOpenAI  — unified LLM interface over gpt-4o-mini
  - Langfuse CallbackHandler     — automatic tracing of every LLM call
  - tenacity                     — retry on transient 429 / 5xx errors

All heavy imports (langchain_openai, langfuse) are deferred to first use so
that simply importing this module does NOT load the LangChain ecosystem.
This avoids multi-second startup delays when the Routing or Base agents are
imported at test time or before the full server boots.

Model selection:
  tier="coordinator" → settings.llm.model_coordinator (gpt-4o-mini)
  tier="insight"     → settings.llm.model_insight     (gpt-4o-mini)
  tier="support"     → settings.llm.model_support     (gpt-4o-mini)

Langfuse observability:
  Set LANGFUSE_ENABLED=true in .env and provide LANGFUSE_PUBLIC_KEY /
  LANGFUSE_SECRET_KEY to see every LLM call in the Langfuse dashboard.
  If disabled or misconfigured, the handler is silently omitted.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from configs.settings import settings
from shared.contracts.agent_output import TokenUsage

# TYPE_CHECKING guard keeps the annotation available for IDEs without
# triggering an import at runtime.
if TYPE_CHECKING:
    from langchain_core.messages import AIMessage, BaseMessage


@dataclass
class LLMResponse:
    content: str
    token_usage: TokenUsage
    model: str
    latency_ms: float


def _is_retryable(exc: BaseException) -> bool:
    """Return True only for transient server-side or rate-limit errors."""
    try:
        from openai import APIConnectionError, APIStatusError
        if isinstance(exc, APIStatusError):
            return exc.status_code in (429, 500, 502, 503, 504)
        return isinstance(exc, APIConnectionError)
    except ImportError:
        return False


def _make_langfuse_handler() -> Any | None:
    """Create a Langfuse LangChain callback handler if observability is enabled."""
    if not settings.langfuse.enabled:
        return None
    try:
        from langfuse.callback import CallbackHandler
        return CallbackHandler(
            public_key=settings.langfuse.public_key,
            secret_key=settings.langfuse.secret_key,
            host=settings.langfuse.host,
        )
    except Exception:
        return None


class LLMClient:
    """LangChain ChatOpenAI wrapper — one instance per agent.

    Usage:
        client = LLMClient(tier="insight")
        response = await client.complete(system="...", messages=[...])

    LangChain and Langfuse are imported lazily on first instantiation to
    keep module-level import time fast.
    """

    _TIER_TO_MODEL: dict[str, str] | None = None

    def __init__(self, model: str | None = None, tier: str = "support") -> None:
        if LLMClient._TIER_TO_MODEL is None:
            LLMClient._TIER_TO_MODEL = {
                "coordinator": settings.llm.model_coordinator,
                "insight":     settings.llm.model_insight,
                "support":     settings.llm.model_support,
            }
        self.model = model or LLMClient._TIER_TO_MODEL.get(tier, settings.llm.model_support)

        # ChatOpenAI is created lazily on the first complete() call so that
        # importing or instantiating any agent never triggers tiktoken download
        # or the full LangChain import chain at startup / test time.
        self._base_llm: Any | None = None

        # Langfuse callback — None when observability is disabled
        self._langfuse_handler: Any | None = _make_langfuse_handler()

    def _get_llm(self) -> Any:
        """Lazy-create ChatOpenAI on first use — keeps __init__ import-free."""
        if self._base_llm is None:
            # Set proxy env vars before httpx initialises its transport so that
            # Windows winreg proxy auto-detection is bypassed (causes hang).
            import os
            os.environ.setdefault("NO_PROXY", "*")
            os.environ.setdefault("HTTP_PROXY", "")
            os.environ.setdefault("HTTPS_PROXY", "")

            from langchain_openai import ChatOpenAI
            self._base_llm = ChatOpenAI(
                model=self.model,
                api_key=settings.llm.openai_api_key,
            )
        return self._base_llm

    async def complete(
        self,
        system: str,
        messages: list[dict],
        max_tokens: int = 1500,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> LLMResponse:
        """Call the LLM via LangChain and return a structured response.

        Args:
            system:      System prompt (role + output format instructions).
            messages:    Conversation turns — list of {"role": ..., "content": ...}.
            max_tokens:  Token cap for the response.
            temperature: Sampling temperature.
            json_mode:   Activates OpenAI JSON output mode when True.

        Returns:
            LLMResponse with text content, token counts, model name, and latency.
        """
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        lc_messages: list[Any] = [SystemMessage(content=system)]
        for m in messages:
            role, content = m.get("role", "user"), m.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))

        # Bind per-call parameters — _get_llm() creates ChatOpenAI on first call
        # response_format is passed as a direct kwarg (not nested in model_kwargs)
        # because newer langchain-openai versions forward top-level kwargs to create().
        bind_kwargs: dict[str, Any] = {"max_tokens": max_tokens, "temperature": temperature}
        if json_mode:
            bind_kwargs["response_format"] = {"type": "json_object"}
        llm: Any = self._get_llm().bind(**bind_kwargs)

        callbacks = [self._langfuse_handler] if self._langfuse_handler else []
        config: dict = {"callbacks": callbacks} if callbacks else {}

        start = time.monotonic()
        ai_msg: Any = await self._invoke_with_retry(llm, lc_messages, config)
        latency_ms = (time.monotonic() - start) * 1000

        # Extract token usage from LangChain response metadata
        usage = getattr(ai_msg, "usage_metadata", None) or {}
        token_usage = TokenUsage(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

        return LLMResponse(
            content=ai_msg.content,
            token_usage=token_usage,
            model=self.model,
            latency_ms=latency_ms,
        )

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _invoke_with_retry(
        self,
        llm: Any,
        messages: list[Any],
        config: dict,
    ) -> Any:
        """Isolated LLM call — retry decorator wraps only the network boundary."""
        return await llm.ainvoke(messages, config=config)
