from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InferenceUnavailable(RuntimeError):
    """The configured model endpoint could not produce a usable response."""


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


class ToolClient(Protocol):
    async def call_tool(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
    ) -> ToolCall: ...


@dataclass(frozen=True, slots=True)
class OpenAICompatibleToolClient:
    base_url: str
    model: str
    api_key: str
    timeout_seconds: float = 30.0

    async def call_tool(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
    ) -> ToolCall:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "tools": tools,
            "tool_choice": "required",
            "temperature": 0,
            "max_tokens": 512,
        }
        response = await asyncio.to_thread(self._post, payload)
        try:
            message = response["choices"][0]["message"]
            calls = message["tool_calls"]
            if len(calls) != 1:
                raise ValueError("expected exactly one tool call")
            function = calls[0]["function"]
            arguments = function["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if not isinstance(function["name"], str) or not isinstance(arguments, dict):
                raise TypeError("invalid tool-call fields")
            return ToolCall(name=function["name"], arguments=arguments)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise InferenceUnavailable("The query model returned an invalid tool call") from error

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                body = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise InferenceUnavailable("The query model is temporarily unavailable") from error
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as error:
            raise InferenceUnavailable("The query model returned invalid JSON") from error
        if not isinstance(decoded, dict):
            raise InferenceUnavailable("The query model returned an invalid response")
        return decoded
