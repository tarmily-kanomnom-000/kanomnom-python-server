"""
OpenAI-compatible API client for various providers.
"""

import logging
import os
from enum import Enum

import requests

logger = logging.getLogger(__name__)


class APIBackend(Enum):
    """Enumeration of supported API backends."""

    OPENAI = "openai"
    OPENWEBUI = "openwebui"
    ANTHROPIC = "anthropic"


class OpenAICompatibleClient:
    """OpenAI-compatible API client for various providers."""

    def __init__(
        self, base_url: str, api_key: str, model: str, backend: APIBackend = None
    ):
        """
        Initialize API client.

        Args:
            base_url: Base URL for the API (e.g., "https://api.openai.com/v1" or "https://your-openwebui.com")
            api_key: API key for authentication
            model: Model name to use
            backend: Which backend this client is for
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.backend = backend or APIBackend.OPENAI

    def __call__(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        """
        Make API call compatible with OpenAI format.

        Args:
            messages: list of message dictionaries with 'role' and 'content'
            max_tokens: Maximum tokens in response

        Returns:
            Response text content
        """
        if self.backend == APIBackend.ANTHROPIC:
            return self._call_anthropic(messages, max_tokens)
        else:
            return self._call_openai_compatible(messages, max_tokens)

    def _call_anthropic(
        self, messages: list[dict[str, str]], max_tokens: int = 1024
    ) -> str:
        """Call Anthropic API with its specific format."""
        # Convert OpenAI format to Anthropic format
        system_message = ""
        user_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "messages": user_messages,
        }

        if system_message:
            payload["system"] = system_message

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        try:
            endpoint = f"{self.base_url}/messages"

            response = requests.post(
                endpoint, headers=headers, json=payload, timeout=120
            )

            if response.status_code == 200:
                result = response.json()
                if "content" in result and len(result["content"]) > 0:
                    return result["content"][0]["text"].strip()
                else:
                    logger.error(f"Unexpected Anthropic response format: {result}")
                    return ""
            else:
                logger.error(
                    f"Anthropic API error: {response.status_code} - {response.text}"
                )
                return ""

        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return ""

    def _call_openai_compatible(
        self, messages: list[dict[str, str]], max_tokens: int = 1024
    ) -> str:
        """Call OpenAI-compatible APIs."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,
            "stream": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            # Use different endpoints for different providers
            if "api.openai.com" in self.base_url:
                endpoint = f"{self.base_url}/chat/completions"
            else:
                endpoint = f"{self.base_url}/api/chat/completions"

            response = requests.post(
                endpoint, headers=headers, json=payload, timeout=120
            )

            if response.status_code == 200:
                result = response.json()

                # Handle different response formats
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"].strip()
                elif "message" in result:
                    return result["message"].strip()
                elif "content" in result:
                    return result["content"].strip()
                else:
                    logger.error(f"Unexpected API response format: {result}")
                    return ""
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return ""

        except Exception as e:
            logger.error(f"Error calling API: {e}")
            return ""


def create_openai_client(
    backend: APIBackend = None,
    base_url: str = None,
    api_key: str = None,
    model: str = None,
) -> OpenAICompatibleClient:
    """
    Create an OpenAI-compatible API client with backend selection.

    Args:
        backend: Which API backend to use (APIBackend.OPENAI or APIBackend.OPENWEBUI)
        base_url: API base URL (overrides backend default)
        api_key: API key (overrides backend default)
        model: Model name (overrides backend default)

    Returns:
        OpenAI-compatible API client
    """
    # Default to OpenAI if no backend specified
    if backend is None:
        backend = APIBackend.OPENAI

    # Set defaults based on backend
    if backend == APIBackend.OPENAI:
        if not base_url:
            base_url = "https://api.openai.com/v1"
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
        if not model:
            model = "gpt-4o"
    elif backend == APIBackend.OPENWEBUI:
        if not base_url:
            base_url = os.getenv("OPENWEBUI_URL", "http://localhost:3000")
        if not api_key:
            api_key = os.getenv("OPENWEBUI_API_KEY")
        if not model:
            model = "qwen3:0.6b"
    elif backend == APIBackend.ANTHROPIC:
        if not base_url:
            base_url = "https://api.anthropic.com/v1"
        if not api_key:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if not model:
            model = "claude-3-5-haiku-20241022"

    if not api_key:
        logger.warning(
            f"No API key provided for {backend.value}. Set appropriate environment variable."
        )

    logger.info(
        f"Creating {backend.value} client with base_url: {base_url}, model: {model}"
    )

    return OpenAICompatibleClient(base_url, api_key, model, backend)
