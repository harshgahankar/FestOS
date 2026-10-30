"""Provider abstraction for LLMs and Embeddings."""
import os
from abc import ABC, abstractmethod
from typing import Any, Optional
import httpx

from app import config as C


class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        """Returns dict with 'content', 'model', 'provider', 'is_deterministic'."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass


class OpenAICompatibleProvider(BaseLLMProvider):
    is_deterministic: bool = False

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.api_key = api_key or C.FESTOS_LLM_API_KEY
        self.base_url = (base_url or C.FESTOS_LLM_BASE_URL).rstrip("/")
        self.model = model or C.FESTOS_LLM_MODEL
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError(
                "FESTOS_LLM_API_KEY is not configured. Falling back to deterministic mode."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"LLM provider error (status {resp.status_code}): {resp.text}"
                )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {
                "content": content,
                "model": self.model,
                "provider": "openai_compatible",
                "is_deterministic": False,
            }


class DeterministicFallbackProvider(BaseLLMProvider):
    """Fallback provider used when no API key is provided or AI is disabled.

    Answers strictly using authoritative facts from the database retrieval service
    and domain event-planning expertise from the event knowledge engine.
    """
    is_deterministic: bool = True

    def is_configured(self) -> bool:
        return True

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        from app.ai.event_knowledge import get_general_event_advice

        user_query = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_query = m.get("content", "")
                break

        advice = get_general_event_advice(user_query)
        return {
            "content": advice,
            "model": "deterministic-festos-engine",
            "provider": "deterministic_fallback",
            "is_deterministic": True,
        }



def get_llm_provider() -> BaseLLMProvider:
    if not C.FESTOS_AI_ENABLED:
        return DeterministicFallbackProvider()

    provider_type = (C.FESTOS_LLM_PROVIDER or "").lower()
    if provider_type == "openai_compatible":
        provider = OpenAICompatibleProvider()
        if provider.is_configured():
            return provider
    return DeterministicFallbackProvider()
