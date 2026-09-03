"""
Minimal Anthropic-style adapter backed by Ollama's local /api/chat endpoint.

Supports what the Day 2 labs need:
- messages.create(...)
- messages.count_tokens(...)
- text blocks
- tool_use blocks
- tool_result input
- response.stop_reason
- response.usage.input_tokens/output_tokens

No paid API key is required.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


class OllamaAnthropic:
    def __init__(self, model: str = "qwen2.5:7b",
                 host: str = "http://localhost:11434",
                 temperature: float = 0.0):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.messages = _Messages(self)

    def _post(self, path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.host + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Cannot reach Ollama at {self.host}: {exc}. "
                "Start it with `ollama serve`."
            ) from exc


class _Messages:
    def __init__(self, client: OllamaAnthropic):
        self.client = client

    @staticmethod
    def _convert_tools(tools):
        if not tools:
            return None
        converted = []
        for tool in tools:
            converted.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {
                        "type": "object", "properties": {}
                    }),
                },
            })
        return converted

    @staticmethod
    def _anthropic_to_ollama(messages, system=None):
        out = []
        if system:
            out.append({"role": "system", "content": system})

        # Map tool ids to names so tool_result messages can carry tool_name.
        tool_names = {}

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                out.append({"role": role, "content": content})
                continue

            if role == "assistant" and isinstance(content, list):
                texts = []
                calls = []
                for block in content:
                    btype = getattr(block, "type", None)
                    if btype == "text":
                        texts.append(getattr(block, "text", ""))
                    elif btype == "tool_use":
                        bid = getattr(block, "id", str(uuid.uuid4()))
                        bname = getattr(block, "name")
                        binput = getattr(block, "input", {})
                        tool_names[bid] = bname
                        calls.append({
                            "function": {
                                "name": bname,
                                "arguments": binput,
                            }
                        })
                item = {"role": "assistant", "content": "\n".join(texts)}
                if calls:
                    item["tool_calls"] = calls
                out.append(item)
                continue

            if role == "user" and isinstance(content, list):
                # Anthropic groups parallel tool results in one user turn.
                # Ollama represents each tool result as a tool-role message.
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        item = {
                            "role": "tool",
                            "content": str(block.get("content", "")),
                        }
                        name = tool_names.get(block.get("tool_use_id"))
                        if name:
                            item["tool_name"] = name
                        out.append(item)
                    else:
                        out.append({"role": "user", "content": str(block)})
                continue

            out.append({"role": role, "content": str(content)})

        return out

    def create(self, model=None, max_tokens=2048, messages=None, tools=None,
               system=None, output_config=None, cache_control=None, **kwargs):
        ollama_messages = self._anthropic_to_ollama(messages or [], system=system)
        payload = {
            "model": self.client.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": self.client.temperature,
                "num_predict": max_tokens,
            },
        }

        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools

        data = self.client._post("/api/chat", payload)
        message = data.get("message") or {}
        blocks = []

        text = message.get("content") or ""
        if text:
            blocks.append(TextBlock(text=text))

        tool_calls = message.get("tool_calls") or []
        for call in tool_calls:
            function = call.get("function") or {}
            args = function.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            blocks.append(ToolUseBlock(
                id=call.get("id") or f"ollama-{uuid.uuid4()}",
                name=function.get("name", ""),
                input=args,
            ))

        stop_reason = "tool_use" if tool_calls else "end_turn"
        usage = SimpleNamespace(
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
        )
        return SimpleNamespace(
            content=blocks,
            stop_reason=stop_reason,
            usage=usage,
            raw=data,
        )

    def count_tokens(self, model=None, messages=None, system=None, tools=None, **kwargs):
        """Use a real local prompt evaluation and return Ollama's prompt token count."""
        ollama_messages = self._anthropic_to_ollama(messages or [], system=system)
        payload = {
            "model": self.client.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 1,
            },
        }
        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools
        data = self.client._post("/api/chat", payload)
        return SimpleNamespace(input_tokens=int(data.get("prompt_eval_count") or 0))
