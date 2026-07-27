"""Production HTTP composition with governed semantics closed."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .application_runtime import ApplicationRuntime, build_application_runtime
from .problems import runtime_problem
from .runtime_config import RuntimeConfig


def create_app() -> FastAPI:
    """Build production solely from one environment snapshot."""
    runtime = build_application_runtime(RuntimeConfig.from_env())
    return _production_app(runtime)


def _production_app(runtime: ApplicationRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        runtime.close()

    app = FastAPI(
        title="OFARM2 Kernel",
        description="Production authentication runtime.",
        version="m2.0",
        lifespan=lifespan,
    )
    app.state.runtime_metadata = runtime.metadata

    @app.get("/health")
    def health():
        return {"status": "ok", "runtime": runtime.metadata.as_dict()}

    @app.get("/manifest")
    def manifest():
        return {
            "runtime": runtime.metadata.as_dict(),
            "protectedSurface": "GOVERNED_SURFACE_BLOCKED",
        }

    def blocked():
        raise HTTPException(
            status_code=503,
            detail=runtime_problem(
                "GOVERNED_SURFACE_BLOCKED",
                "Governed production surface unavailable",
                "tenant binding is ready; downstream governed semantics remain closed",
                problem_id="problem:governed-surface-blocked",
            ),
        )

    for path, method in (
        ("/commit", "POST"),
        ("/review/accept", "POST"),
        ("/review/reject", "POST"),
        ("/review/contest", "POST"),
        ("/records/{record_id}", "GET"),
        ("/views/passport/{farm_ref}", "GET"),
        ("/views/inspection-register/freeze", "POST"),
    ):
        app.add_api_route(path, blocked, methods=[method])
    return app
