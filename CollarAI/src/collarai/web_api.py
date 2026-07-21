from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from hmac import compare_digest
from time import perf_counter

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from collarai.credentials import AccessTokenStore
from collarai.inference import InferenceUnavailable
from collarai.models import RunStatus
from collarai.query import QueryAnswer, QueryInput, QueryRejected, QueryRouter, format_answer
from collarai.service import BrowserService, build_service

DEFAULT_ORIGINS = (
    "https://frankyzha.github.io",
    "http://127.0.0.1:4000",
    "http://localhost:4000",
)
_DEFAULT_TOKEN = object()


def create_app(
    service_factory: Callable[[], BrowserService] = build_service,
    access_token: str | None | object = _DEFAULT_TOKEN,
    router: QueryRouter | None = None,
) -> FastAPI:
    expected_token = AccessTokenStore().load() if access_token is _DEFAULT_TOKEN else access_token
    require_auth = bool(expected_token) or _env_bool("COLLAR_API_REQUIRE_AUTH")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.browser = service_factory()
        try:
            yield
        finally:
            await app.state.browser.close()

    app = FastAPI(
        title="CollarAI Demo API",
        version="0.3.0",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.router = router or QueryRouter()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(QueryRejected)
    async def rejected(_: Request, error: QueryRejected) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": error.code.value, "message": str(error)}},
        )

    @app.exception_handler(InferenceUnavailable)
    async def model_unavailable(_: Request, error: InferenceUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "model_unavailable",
                    "message": str(error),
                }
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "authentication": "required" if require_auth else "disabled"}

    @app.post("/api/query", response_model=QueryAnswer)
    async def query(payload: QueryInput, request: Request) -> QueryAnswer | JSONResponse:
        if require_auth and not _authorized(request, expected_token):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "unauthorized",
                        "message": "A valid demo access key is required.",
                    }
                },
            )
        started = perf_counter()
        routed = await app.state.router.parse(payload.query)
        result = await request.app.state.browser.analyze_financing_transactions(routed.request)
        elapsed_ms = round((perf_counter() - started) * 1_000)
        if result.status is RunStatus.COMPLETE:
            return format_answer(payload.query, result, elapsed_ms)

        status_codes = {
            RunStatus.NEEDS_HUMAN: 409,
            RunStatus.NEEDS_CONFIGURATION: 501,
            RunStatus.FAILED: 502,
        }
        return JSONResponse(
            status_code=status_codes[result.status],
            content={
                "error": {
                    "code": result.status.value,
                    "message": _public_error_message(result.status, result.message),
                    "run_id": result.run_id,
                }
            },
        )

    return app


def _allowed_origins() -> list[str]:
    configured = os.getenv("COLLAR_API_ORIGINS")
    if not configured:
        return list(DEFAULT_ORIGINS)
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").casefold() in {"1", "true", "yes", "on"}


def _authorized(request: Request, expected_token: str | None | object) -> bool:
    if not isinstance(expected_token, str) or not expected_token:
        return False
    scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
    return scheme.casefold() == "bearer" and compare_digest(supplied, expected_token)


def _public_error_message(status: RunStatus, detail: str | None) -> str:
    if status in {RunStatus.NEEDS_HUMAN, RunStatus.NEEDS_CONFIGURATION} and detail:
        return detail
    return "The browser session could not complete the query. Please retry."


app = create_app()


def main() -> None:
    host = os.getenv("COLLAR_API_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "localhost"} and not os.getenv("COLLAR_ALLOW_PUBLIC_API"):
        raise RuntimeError(
            "Refusing to expose the authenticated browser API directly. "
            "Keep it on loopback behind an authenticated HTTPS proxy, or explicitly set "
            "COLLAR_ALLOW_PUBLIC_API=1."
        )
    uvicorn.run(
        "collarai.web_api:app",
        host=host,
        port=int(os.getenv("COLLAR_API_PORT", "8787")),
        log_level=os.getenv("COLLAR_API_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
