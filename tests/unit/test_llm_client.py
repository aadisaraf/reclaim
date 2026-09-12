import json

import httpx2
import pytest
from openai import APIStatusError, RateLimitError
from pydantic import BaseModel

from reclaim.adapters.llm import OpenAiLlmClient, ReplayLlmClient, cost_usd, replay_key
from reclaim.adapters.protocols import LlmUsage, ReplayMissError
from reclaim.config import Settings


class Dummy(BaseModel):
    value: str


# ---- ReplayLlmClient ----

def test_replay_returns_output_and_usage(tmp_path):
    key = replay_key("gpt-5.6-luna", "medium", "do the thing", [{"role": "user", "content": "hi"}])
    step_dir = tmp_path / "build_matrix"
    step_dir.mkdir()
    (step_dir / f"{key}.json").write_text(json.dumps({
        "output": {"value": "hello"},
        "usage": {"input_tokens": 10, "cached_tokens": 0, "output_tokens": 5, "reasoning_tokens": 1},
    }))
    client = ReplayLlmClient(tmp_path, "gpt-5.6-luna")
    import asyncio
    result = asyncio.run(client.parse(
        step="build_matrix", instructions="do the thing", input=[{"role": "user", "content": "hi"}],
        text_format=Dummy, effort="medium", max_output_tokens=100, prompt_cache_key="p",
    ))
    assert result.output.value == "hello"
    assert result.usage.input_tokens == 10
    assert result.mode == "replay"


def test_replay_miss_raises_naming_step(tmp_path):
    client = ReplayLlmClient(tmp_path, "gpt-5.6-luna")
    import asyncio
    with pytest.raises(ReplayMissError) as exc_info:
        asyncio.run(client.parse(
            step="build_matrix", instructions="x", input=[], text_format=Dummy,
            effort="medium", max_output_tokens=100, prompt_cache_key="p",
        ))
    assert exc_info.value.step == "build_matrix"


def test_replay_malformed_output_fails_validation(tmp_path):
    key = replay_key("gpt-5.6-luna", "medium", "x", [])
    step_dir = tmp_path / "build_matrix"
    step_dir.mkdir()
    (step_dir / f"{key}.json").write_text(json.dumps({
        "output": {"wrong_field": 1},
        "usage": {"input_tokens": 1, "cached_tokens": 0, "output_tokens": 1, "reasoning_tokens": 0},
    }))
    client = ReplayLlmClient(tmp_path, "gpt-5.6-luna")
    import asyncio
    with pytest.raises(Exception):
        asyncio.run(client.parse(
            step="build_matrix", instructions="x", input=[], text_format=Dummy,
            effort="medium", max_output_tokens=100, prompt_cache_key="p",
        ))


def test_replay_key_changes_with_inputs():
    base = replay_key("gpt-5.6-luna", "medium", "instructions", [{"a": 1}])
    assert base != replay_key("other-model", "medium", "instructions", [{"a": 1}])
    assert base != replay_key("gpt-5.6-luna", "high", "instructions", [{"a": 1}])
    assert base != replay_key("gpt-5.6-luna", "medium", "different", [{"a": 1}])
    assert base != replay_key("gpt-5.6-luna", "medium", "instructions", [{"a": 2}])


# ---- OpenAiLlmClient ----

class FakeResponses:
    def __init__(self):
        self.calls = []
        self.behaviors = []

    def queue(self, behavior):
        self.behaviors.append(behavior)

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        behavior = self.behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


class FakeOpenAI:
    def __init__(self):
        self.responses = FakeResponses()


def make_fake_response(status="completed", value="hi", input_tokens=100, cached_tokens=20,
                        output_tokens=50, reasoning_tokens=10):
    class Usage:
        def __init__(self):
            self.input_tokens = input_tokens
            self.output_tokens = output_tokens
            self.input_tokens_details = type("X", (), {"cached_tokens": cached_tokens})()
            self.output_tokens_details = type("X", (), {"reasoning_tokens": reasoning_tokens})()

    class Response:
        def __init__(self):
            self.status = status
            self.incomplete_details = "ran out of tokens" if status == "incomplete" else None
            self.output_parsed = Dummy(value=value)
            self.usage = Usage()

    return Response()


def make_client():
    client = OpenAiLlmClient(api_key="sk-test", model="gpt-5.6-luna")
    fake = FakeOpenAI()
    client.client = fake
    return client, fake


def test_calls_with_required_params():
    import asyncio

    client, fake = make_client()
    fake.responses.queue(make_fake_response())
    asyncio.run(client.parse(
        step="build_matrix", instructions="do it", input=[{"role": "user", "content": "x"}],
        text_format=Dummy, effort="medium", max_output_tokens=6000, prompt_cache_key="policy-1",
    ))
    call = fake.responses.calls[0]
    assert call["store"] is False
    assert call["reasoning"] == {"effort": "medium"}
    assert call["max_output_tokens"] == 6000
    assert call["prompt_cache_key"] == "policy-1"
    assert call["text_format"] is Dummy


def test_retries_once_on_429():
    import asyncio

    client, fake = make_client()
    resp = httpx2.Response(429, request=httpx2.Request("POST", "http://x"))
    fake.responses.queue(RateLimitError("rate limited", response=resp, body=None))
    fake.responses.queue(make_fake_response())
    result = asyncio.run(client.parse(
        step="build_matrix", instructions="x", input=[], text_format=Dummy,
        effort="medium", max_output_tokens=100, prompt_cache_key="p",
    ))
    assert result.output.value == "hi"
    assert len(fake.responses.calls) == 2


def test_retries_once_on_500():
    import asyncio

    client, fake = make_client()
    resp = httpx2.Response(500, request=httpx2.Request("POST", "http://x"))
    fake.responses.queue(APIStatusError("server error", response=resp, body=None))
    fake.responses.queue(make_fake_response())
    result = asyncio.run(client.parse(
        step="build_matrix", instructions="x", input=[], text_format=Dummy,
        effort="medium", max_output_tokens=100, prompt_cache_key="p",
    ))
    assert result.output.value == "hi"


def test_never_retries_on_400():
    import asyncio

    client, fake = make_client()
    resp = httpx2.Response(400, request=httpx2.Request("POST", "http://x"))
    fake.responses.queue(APIStatusError("bad request", response=resp, body=None))
    with pytest.raises(APIStatusError):
        asyncio.run(client.parse(
            step="build_matrix", instructions="x", input=[], text_format=Dummy,
            effort="medium", max_output_tokens=100, prompt_cache_key="p",
        ))
    assert len(fake.responses.calls) == 1


def test_incomplete_status_raises():
    import asyncio

    client, fake = make_client()
    fake.responses.queue(make_fake_response(status="incomplete"))
    with pytest.raises(RuntimeError):
        asyncio.run(client.parse(
            step="build_matrix", instructions="x", input=[], text_format=Dummy,
            effort="medium", max_output_tokens=100, prompt_cache_key="p",
        ))


def test_usage_mapping():
    import asyncio

    client, fake = make_client()
    fake.responses.queue(make_fake_response(input_tokens=100, cached_tokens=20, output_tokens=50, reasoning_tokens=10))
    result = asyncio.run(client.parse(
        step="build_matrix", instructions="x", input=[], text_format=Dummy,
        effort="medium", max_output_tokens=100, prompt_cache_key="p",
    ))
    assert result.usage.input_tokens == 100
    assert result.usage.cached_tokens == 20
    assert result.usage.output_tokens == 50
    assert result.usage.reasoning_tokens == 10


def test_cost_usd():
    settings = Settings()
    usage = LlmUsage(input_tokens=1_000_000, cached_tokens=200_000, output_tokens=500_000, reasoning_tokens=0)
    expected = (800_000 * 0.20 / 1_000_000) + (200_000 * 0.02 / 1_000_000) + (500_000 * 1.20 / 1_000_000)
    assert cost_usd(usage, settings) == pytest.approx(expected)


def test_recording_writes_only_required_fields(tmp_path):
    import asyncio

    client = OpenAiLlmClient(api_key="sk-test", model="gpt-5.6-luna", record_dir=tmp_path)
    fake = FakeOpenAI()
    client.client = fake
    fake.responses.queue(make_fake_response())
    asyncio.run(client.parse(
        step="build_matrix", instructions="x", input=[], text_format=Dummy,
        effort="medium", max_output_tokens=100, prompt_cache_key="p",
    ))
    files = list((tmp_path / "build_matrix").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert set(data.keys()) == {"step", "key", "model", "effort", "output", "usage"}
