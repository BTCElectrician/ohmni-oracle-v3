"""
Regression tests ensuring Chat Completions parameters stay consistent across models.
"""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.ai_service import make_chat_completion_request


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeUsage:
    prompt_tokens = 10
    completion_tokens = 20
    total_tokens = 30


class _FakeResponse:
    def __init__(self, content: str = '{"ok": true}'):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()
        self.id = "chatcmpl-test"
        self.model = "gpt-4.1-mini"


def _build_client(fake_response: _FakeResponse) -> Mock:
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    client.chat.completions.create = AsyncMock(return_value=fake_response)
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize("model_name", ["gpt-4.1-mini", "gpt-5-mini"])
async def test_all_models_request_json_response_format(model_name: str) -> None:
    """All chat completion calls must enforce JSON output formatting."""
    client = _build_client(_FakeResponse())

    await make_chat_completion_request(
        client=client,
        input_text="test input",
        model=model_name,
        temperature=0.2,
        max_tokens=128,
        file_path="/tmp/test.pdf",
        drawing_type="Architectural",
        instructions="Return JSON.",
    )

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["model"] == model_name
    assert kwargs["max_tokens"] == 128


@pytest.mark.asyncio
async def test_chat_completion_returns_message_content() -> None:
    """Helper should surface the string content produced by the API."""
    fake_content = '{"rooms": []}'
    client = _build_client(_FakeResponse(content=fake_content))

    result = await make_chat_completion_request(
        client=client,
        input_text="extract rooms",
        model="gpt-4.1-mini",
        temperature=0.0,
        max_tokens=256,
        file_path="drawing.pdf",
        drawing_type="Architectural",
        instructions="Return JSON.",
    )

    assert result == fake_content
