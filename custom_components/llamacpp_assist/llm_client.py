"""LLM client abstraction for llama.cpp server."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class LlamaCppClient:
    """Client for llama.cpp server chat completions (no tool calling)."""
    
    def __init__(
        self,
        server_url: str,
        api_key: str | None,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the LLM client."""
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.session = session
    
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        timeout: int = 30,
    ) -> str:
        """
        Simple chat completion without tool calling.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
        
        Returns:
            The assistant's response content as a string
        
        Raises:
            asyncio.TimeoutError: If request times out
            aiohttp.ClientError: If HTTP request fails
            ValueError: If response format is invalid
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        _LOGGER.debug(
            "LLM chat request: %d messages, temp=%.2f, max_tokens=%d",
            len(messages),
            temperature,
            max_tokens,
        )
        
        try:
            async with asyncio.timeout(timeout):
                async with self.session.post(
                    f"{self.server_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise ValueError(
                            f"LLM server returned status {response.status}: {error_text}"
                        )
                    
                    data = await response.json()
        except asyncio.TimeoutError:
            _LOGGER.error("LLM request timed out after %d seconds", timeout)
            raise
        except aiohttp.ClientError as err:
            _LOGGER.error("LLM request failed: %s", err)
            raise
        
        # Extract response content
        if "choices" not in data or not data["choices"]:
            raise ValueError("Invalid LLM response: no choices")
        
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content", "")
        
        if not content:
            _LOGGER.warning("LLM returned empty content")
        
        _LOGGER.debug("LLM response: %d characters", len(content))
        
        return content.strip()
    
    async def parse_json_response(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """
        Chat completion with JSON parsing and error recovery.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
        
        Returns:
            Parsed JSON response as a dictionary
        
        Raises:
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        content = await self.chat(messages, temperature, max_tokens, timeout)
        
        # Try to extract JSON from markdown code blocks if present
        if "```json" in content:
            # Extract content between ```json and ```
            start = content.index("```json") + 7
            end = content.index("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            # Try generic code block
            start = content.index("```") + 3
            # Skip language identifier if present
            if "\n" in content[start:]:
                start = content.index("\n", start) + 1
            end = content.index("```", start)
            content = content[start:end].strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse LLM JSON response: %s", content[:200])
            raise ValueError(f"Invalid JSON response from LLM: {err}") from err
