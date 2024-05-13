import os
from typing import Any, AsyncGenerator, Generator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from llama_index.core.base.llms.types import ChatMessage, LLMMetadata
from llama_index.llms.nvidia import NVIDIA

from openai.types.chat.chat_completion import (
    ChatCompletion,
    ChatCompletionMessage,
    Choice,
    ChoiceLogprobs,
)
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk, ChoiceDelta
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from openai.types.completion import Completion, CompletionUsage


class CachedNVIDIApiKeys:
    def __init__(self, set_env_key_to: Optional[str] = "", set_fake_key: bool = False):
        self.set_env_key_to = set_env_key_to
        self.set_fake_key = set_fake_key

    def __enter__(self) -> None:
        self.api_env_was = os.environ.get("NVIDIA_API_KEY", "")
        os.environ["NVIDIA_API_KEY"] = self.set_env_key_to

        if self.set_fake_key:
            os.environ["NVIDIA_API_KEY"] = "nvai-" + "x" * 9 + "-" + "x" * 54

    def __exit__(self, *exc: object) -> None:
        if self.api_env_was == "":
            del os.environ["NVIDIA_API_KEY"]
        else:
            os.environ["NVIDIA_API_KEY"] = self.api_env_was


def mock_chat_completion_v1(*args: Any, **kwargs: Any) -> ChatCompletion:
    return ChatCompletion(
        id="chatcmpl-4162e407-e121-42b4-8590-1c173380be7d",
        object="chat.completion",
        created=1713474384,
        model="mistralai/mistral-7b-instruct-v0.2",
        usage=CompletionUsage(
            completion_tokens=304, prompt_tokens=11, total_tokens=315
        ),
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                logprobs=ChoiceLogprobs(
                    content=None,
                    text_offset=[],
                    token_logprobs=[0.0, 0.0],
                    tokens=[],
                    top_logprobs=[],
                ),
                message=ChatCompletionMessage(
                    content="Cool Test Message",
                    role="assistant",
                    function_call=None,
                    tool_calls=None,
                ),
            )
        ],
    )


async def mock_async_chat_completion_v1(*args: Any, **kwargs: Any) -> Completion:
    return mock_chat_completion_v1(*args, **kwargs)


def mock_chat_completion_stream_v1(
    *args: Any, **kwargs: Any
) -> Generator[ChatCompletionChunk, None, None]:
    responses = [
        ChatCompletionChunk(
            id="chatcmpl-998d9b96-0b71-41f5-b910-dd3bc00f38c6",
            object="chat.completion.chunk",
            created=1713474736,
            model="google/gemma-7b",
            choices=[
                ChunkChoice(
                    finish_reason="stop",
                    index=0,
                    delta=ChoiceDelta(
                        content="Test",
                        function_call=None,
                        role="assistant",
                        tool_calls=None,
                    ),
                )
            ],
        ),
        ChatCompletionChunk(
            id="chatcmpl-998d9b96-0b71-41f5-b910-dd3bc00f38c6",
            object="chat.completion.chunk",
            created=1713474736,
            model="google/gemma-7b",
            choices=[
                ChunkChoice(
                    finish_reason="stop",
                    index=0,
                    delta=ChoiceDelta(
                        content="Second Test",
                        function_call=None,
                        role="assistant",
                        tool_calls=None,
                    ),
                )
            ],
        ),
    ]

    yield from responses


async def mock_async_chat_completion_stream_v1(
    *args: Any, **kwargs: Any
) -> AsyncGenerator[Completion, None]:
    async def gen() -> AsyncGenerator[Completion, None]:
        for response in mock_chat_completion_stream_v1(*args, **kwargs):
            yield response

    return gen()


@patch("llama_index.llms.openai.base.SyncOpenAI")
def test_chat_model_basic(MockSyncOpenAI: MagicMock) -> None:
    with CachedNVIDIApiKeys(set_fake_key=True):
        mock_instance = MockSyncOpenAI.return_value
        mock_instance.chat.completions.create.return_value = mock_chat_completion_v1()

        llm = NVIDIA()
        prompt = "test prompt"
        message = ChatMessage(role="user", content="test message")

        response = llm.complete(prompt)
        assert response.text == "Cool Test Message"

        chat_response = llm.chat([message])
        assert chat_response.message.content == "Cool Test Message"


@patch("llama_index.llms.openai.base.SyncOpenAI")
def test_chat_model_streaming(MockSyncOpenAI: MagicMock) -> None:
    with CachedNVIDIApiKeys(set_fake_key=True):
        mock_instance = MockSyncOpenAI.return_value
        mock_instance.chat.completions.create.return_value = (
            mock_chat_completion_stream_v1()
        )

        llm = NVIDIA()
        prompt = "test prompt"
        message = ChatMessage(role="user", content="test message")

        response_gen = llm.stream_complete(prompt)
        responses = list(response_gen)
        assert responses[-1].text == "TestSecond Test"

        mock_instance.chat.completions.create.return_value = (
            mock_chat_completion_stream_v1()
        )

        chat_response_gen = llm.stream_chat([message])
        chat_responses = list(chat_response_gen)
        print(chat_responses)
        assert chat_responses[-1].message.content == "TestSecond Test"
        assert chat_responses[-1].message.role == "assistant"


@pytest.mark.asyncio()
@patch("llama_index.llms.openai.base.AsyncOpenAI")
async def test_async_chat_model_basic(MockAsyncOpenAI: MagicMock) -> None:
    with CachedNVIDIApiKeys(set_fake_key=True):
        mock_instance = MockAsyncOpenAI.return_value
        create_fn = AsyncMock()
        create_fn.side_effect = mock_async_chat_completion_v1
        mock_instance.chat.completions.create = create_fn

        llm = NVIDIA()
        prompt = "test prompt"
        message = ChatMessage(role="user", content="test message")

        response = await llm.acomplete(prompt)
        assert response.text == "Cool Test Message"

        chat_response = await llm.achat([message])
        assert chat_response.message.content == "Cool Test Message"


@pytest.mark.asyncio()
@patch("llama_index.llms.openai.base.AsyncOpenAI")
async def test_async_streaming_chat_model(MockAsyncOpenAI: MagicMock) -> None:
    with CachedNVIDIApiKeys(set_fake_key=True):
        mock_instance = MockAsyncOpenAI.return_value
        create_fn = AsyncMock()
        create_fn.side_effect = mock_async_chat_completion_stream_v1
        mock_instance.chat.completions.create = create_fn

        llm = NVIDIA()
        prompt = "test prompt"
        message = ChatMessage(role="user", content="test message")

        response_gen = await llm.astream_complete(prompt)
        responses = [response async for response in response_gen]
        assert responses[-1].text == "TestSecond Test"

        chat_response_gen = await llm.astream_chat([message])
        chat_responses = [response async for response in chat_response_gen]
        assert chat_responses[-1].message.content == "TestSecond Test"


def test_validates_api_key_is_present() -> None:
    with CachedNVIDIApiKeys(set_fake_key=True):
        assert NVIDIA()

        os.environ["NVIDIA_API_KEY"] = ""

        assert NVIDIA(api_key="nvai-" + "x" * 9 + "-" + "x" * 54)


def test_metadata() -> None:
    assert isinstance(NVIDIA().metadata, LLMMetadata)
