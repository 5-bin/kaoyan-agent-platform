import secrets
from fastapi import FastAPI, Header, HTTPException
from .runner import Runner
from .schemas import RunRequest, RunResult
from .settings import Settings


def create_app(settings: Settings | None = None, runner: Runner | None = None):
    settings = settings or Settings.from_env()
    settings.validate()
    runner = runner or Runner(settings)
    app = FastAPI(title="考研 Agent 内部接口", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "python-agent", "mode": settings.mode, "releaseId": "demo-408-v1"}

    @app.post("/internal/run", response_model=RunResult)
    def run(body: RunRequest, x_internal_key: str = Header(default="")):
        if not secrets.compare_digest(x_internal_key.encode(), settings.internal_key.encode()):
            raise HTTPException(status_code=401, detail="内部凭证不正确")
        return runner.run(body)

    return app
