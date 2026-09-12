from reclaim.adapters.protocols import BinaryContent, EhrNotFound, RemitFileRef


class FakeInbox:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    async def list_files(self) -> list[RemitFileRef]:
        return [RemitFileRef(name=n, size=len(c), mtime=0) for n, c in self.files.items()]

    async def download(self, name: str) -> bytes:
        return self.files[name]

    async def deliver(self, name: str, content: bytes) -> None:
        self.files[name] = content

    async def clear(self) -> None:
        self.files.clear()


class FakeArchive:
    def __init__(self):
        self.claims: dict[str, bytes] = {}

    async def get_837(self, hospital_claim_id: str) -> bytes | None:
        return self.claims.get(hospital_claim_id)


class SpyEhrClient:
    def __init__(self):
        self.requests_made: list[str] = []

    async def read(self, resource_type: str, resource_id: str) -> dict:
        self.requests_made.append(f"GET /fhir/R4/{resource_type}/{resource_id}")
        raise EhrNotFound(f"{resource_type}/{resource_id}")

    async def search(self, resource_type: str, patient_id: str) -> list[dict]:
        self.requests_made.append(f"GET /fhir/R4/{resource_type}?patient={patient_id}")
        raise EhrNotFound(resource_type)

    async def read_binary(self, binary_id: str) -> BinaryContent:
        self.requests_made.append(f"GET /fhir/R4/Binary/{binary_id}")
        raise EhrNotFound(binary_id)


class FakeLlmClient:
    """Returns queued hand-written outputs; records each call's step, effort, and input."""

    def __init__(self):
        self.queue: list = []
        self.calls: list[dict] = []

    def queue_result(self, output, usage=None):
        from reclaim.adapters.protocols import LlmResult, LlmUsage

        self.queue.append(
            LlmResult(
                output=output,
                usage=usage or LlmUsage(input_tokens=100, cached_tokens=0, output_tokens=50, reasoning_tokens=0),
                mode="replay",
            )
        )

    async def parse(self, *, step, instructions, input, text_format, effort,
                     max_output_tokens, prompt_cache_key):
        self.calls.append({
            "step": step, "effort": effort, "input": input,
            "prompt_cache_key": prompt_cache_key,
        })
        if not self.queue:
            raise RuntimeError(f"FakeLlmClient queue empty for step {step}")
        return self.queue.pop(0)
