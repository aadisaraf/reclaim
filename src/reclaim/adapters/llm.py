import asyncio
import hashlib
import json
import random
from pathlib import Path
from typing import Literal, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from reclaim.adapters.protocols import LlmResult, LlmUsage, ReplayMissError
from reclaim.config import Settings

T = TypeVar("T", bound=BaseModel)
Effort = Literal["low", "medium", "high"]


def replay_key(model: str, effort: str, instructions: str, input: list[dict]) -> str:
    payload = json.dumps(
        {"model": model, "effort": effort, "instructions": instructions, "input": input},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def cost_usd(usage: LlmUsage, settings: Settings) -> float:
    billable_input = usage.input_tokens - usage.cached_tokens
    return (
        billable_input * settings.price_input_per_m / 1_000_000
        + usage.cached_tokens * settings.price_cached_input_per_m / 1_000_000
        + usage.output_tokens * settings.price_output_per_m / 1_000_000
    )


class OpenAiLlmClient:
    """Live: OpenAI Responses API, Structured Outputs, store=false, one 429/5xx retry."""

    def __init__(self, api_key: str, model: str, record_dir: str | Path | None = None):
        self.model = model
        self.client = OpenAI(api_key=api_key).with_options(timeout=45.0, max_retries=0)
        self.record_dir = Path(record_dir) if record_dir else None

    async def parse(
        self, *, step: Literal["build_matrix", "draft_packet"], instructions: str,
        input: list[dict], text_format: type[T], effort: Effort,
        max_output_tokens: int, prompt_cache_key: str,
    ) -> LlmResult:
        def _call():
            return self.client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=input,
                text_format=text_format,
                reasoning={"effort": effort},
                max_output_tokens=max_output_tokens,
                prompt_cache_key=prompt_cache_key,
                store=False,
            )

        response = await self._call_with_retry(_call)

        if response.status == "incomplete":
            raise RuntimeError(f"LLM response incomplete for step {step}: {response.incomplete_details}")

        usage = LlmUsage(
            input_tokens=response.usage.input_tokens,
            cached_tokens=response.usage.input_tokens_details.cached_tokens,
            output_tokens=response.usage.output_tokens,
            reasoning_tokens=response.usage.output_tokens_details.reasoning_tokens,
        )
        result = LlmResult(output=response.output_parsed, usage=usage, mode="live")

        if self.record_dir is not None:
            key = replay_key(self.model, effort, instructions, input)
            self._write_recording(step, key, effort, result)

        return result

    async def _call_with_retry(self, fn):
        from openai import APIStatusError, RateLimitError

        try:
            return await asyncio.to_thread(fn)
        except (RateLimitError,) as exc:
            await asyncio.sleep(0.5 + random.random())
            return await asyncio.to_thread(fn)
        except APIStatusError as exc:
            if exc.status_code >= 500:
                await asyncio.sleep(0.5 + random.random())
                return await asyncio.to_thread(fn)
            raise

    def _write_recording(self, step: str, key: str, effort: str, result: LlmResult) -> None:
        step_dir = self.record_dir / step
        step_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "step": step,
            "key": key,
            "model": self.model,
            "effort": effort,
            "output": result.output.model_dump(mode="json"),
            "usage": result.usage.model_dump(),
        }
        (step_dir / f"{key}.json").write_text(json.dumps(data, indent=2, sort_keys=True))


class ReplayLlmClient:
    """Replay: fixtures/llm-replay/<step>/<key>.json, recorded from a real live run."""

    def __init__(self, directory: str | Path, model: str):
        self.directory = Path(directory)
        self.model = model

    async def parse(
        self, *, step: Literal["build_matrix", "draft_packet"], instructions: str,
        input: list[dict], text_format: type[T], effort: Effort,
        max_output_tokens: int, prompt_cache_key: str,
    ) -> LlmResult:
        key = replay_key(self.model, effort, instructions, input)
        path = self.directory / step / f"{key}.json"
        if not path.exists():
            raise ReplayMissError(step, key)
        data = json.loads(path.read_text())
        output = text_format.model_validate(data["output"])
        usage = LlmUsage(**data["usage"])
        return LlmResult(output=output, usage=usage, mode="replay")
