import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from reclaim.adapters.fhir import HttpEhrClient
from reclaim.adapters.llm import OpenAiLlmClient, ReplayLlmClient
from reclaim.adapters.payer import NorthstarPayerAdapter
from reclaim.adapters.policy import FilePolicyStore
from reclaim.adapters.sftp import SftpClaimArchive, SftpRemitInbox
from reclaim.api import router
from reclaim.config import Settings
from reclaim.context import AppContext
from reclaim.poller import run_inbox_poller, run_tracking_poller
from reclaim.repo import Repo


def create_app(settings: Settings, ctx: AppContext) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ctx.repo.init_schema()
        inbox_task = asyncio.create_task(run_inbox_poller(ctx))
        tracking_task = asyncio.create_task(run_tracking_poller(ctx))
        yield
        inbox_task.cancel()
        tracking_task.cancel()

    app = FastAPI(lifespan=lifespan)
    # Set outside lifespan so tests using a plain ASGITransport (no lifespan trigger) still see it.
    app.state.ctx = ctx
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": str(exc.detail)}},
        )

    return app


def _build_context(settings: Settings) -> AppContext:
    ehr_client = HttpEhrClient(
        base_url=settings.ehr_base_url,
        token_url=settings.ehr_base_url.removesuffix("/fhir/R4") + "/auth/token",
        client_id=settings.hospital_client_id,
        client_secret=settings.hospital_client_secret,
    )
    payer_adapter = NorthstarPayerAdapter(base_url=settings.payer_base_url, token=settings.payer_token)
    policy_store = FilePolicyStore("fixtures/policies")
    llm_client = (
        OpenAiLlmClient(api_key=settings.openai_api_key, model=settings.openai_model)
        if settings.llm_mode == "live"
        else ReplayLlmClient(directory="fixtures/llm-replay", model=settings.openai_model)
    )
    remit_inbox = SftpRemitInbox(settings)
    claim_archive = SftpClaimArchive(settings)
    repo = Repo(settings.database_path)
    return AppContext(
        repo=repo,
        settings=settings,
        remit_inbox=remit_inbox,
        claim_archive=claim_archive,
        ehr_client=ehr_client,
        policy_store=policy_store,
        payer_adapter=payer_adapter,
        llm_client=llm_client,
    )


settings = Settings.from_env()
ctx = _build_context(settings)
app = create_app(settings, ctx)
