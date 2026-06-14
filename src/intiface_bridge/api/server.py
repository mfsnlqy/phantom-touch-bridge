from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from intiface_bridge import __version__
from intiface_bridge.api.routes import router
from intiface_bridge.config import AppSettings, load_settings
from intiface_bridge.errors import BridgeError, ErrorCode, error_result_from_exception
from intiface_bridge.logging import configure_logging, get_logger
from intiface_bridge.models import ErrorResult
from intiface_bridge.service import BridgeService

logger = get_logger(__name__)


class Utf8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"


def create_app(
    settings: AppSettings | None = None,
    *,
    config_path: str | Path | None = None,
    service: BridgeService | None = None,
) -> FastAPI:
    if service is not None:
        resolved_settings = settings or service.settings
        if settings is not None and service.settings != settings:
            raise ValueError("Injected BridgeService settings must match app settings.")
    else:
        resolved_settings = settings or load_settings(config_path=config_path)
    configure_logging(resolved_settings)

    app = FastAPI(
        title="phantom-touch-bridge",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
        default_response_class=Utf8JSONResponse,
    )
    app.state.settings = resolved_settings
    app.state.service = service or BridgeService(resolved_settings)

    @app.exception_handler(BridgeError)
    async def handle_bridge_error(_: Request, error: BridgeError) -> JSONResponse:
        result = error_result_from_exception(
            error,
            include_details=resolved_settings.backend.error_detail == "verbose",
        )
        return Utf8JSONResponse(
            status_code=_status_code_for_error(error.code),
            content=result.model_dump(mode="json", exclude_none=True),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        result = ErrorResult(
            backend=resolved_settings.backend.type,
            code=ErrorCode.COMMAND_FAILED.value,
            error="请求参数无效。",
            details={"errors": error.errors()} if resolved_settings.backend.error_detail == "verbose" else None,
        )
        return Utf8JSONResponse(
            status_code=422,
            content=result.model_dump(mode="json", exclude_none=True),
        )

    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        return {
            "name": "phantom-touch-bridge",
            "version": __version__,
            "backend": resolved_settings.backend.type,
        }

    app.include_router(router)
    logger.debug(
        "FastAPI app created for backend=%s host=%s port=%s",
        resolved_settings.backend.type,
        resolved_settings.bridge.host,
        resolved_settings.bridge.port,
    )
    return app


def run_server(
    settings: AppSettings | None = None,
    *,
    config_path: str | Path | None = None,
) -> None:
    resolved_settings = settings or load_settings(config_path=config_path)
    app = create_app(resolved_settings)
    uvicorn.run(
        app,
        host=resolved_settings.bridge.host,
        port=resolved_settings.bridge.port,
    )


def _status_code_for_error(code: ErrorCode) -> int:
    if code in {ErrorCode.INVALID_STRENGTH}:
        return 400
    if code in {ErrorCode.DEVICE_NOT_FOUND}:
        return 404
    if code in {ErrorCode.MULTIPLE_DEVICES_MATCHED}:
        return 409
    if code in {ErrorCode.BACKEND_UNAVAILABLE, ErrorCode.CONNECT_FAILED}:
        return 503
    if code in {ErrorCode.NOT_CONNECTED}:
        return 409
    return 500


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()

