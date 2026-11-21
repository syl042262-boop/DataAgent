import asyncio
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from starlette.concurrency import run_in_threadpool

from app.agent_datasources import router as bindings_router
from app.agents import router as agents_router
from app.cleanup import cleanup_jobs
from app.config import Settings
from app.database import migrate, open_database
from app.datasources import router as datasources_router
from app.deletion import router as deletion_router
from app.effective_config import router as effective_config_router
from app.history import router as history_router
from app.knowledge import router as knowledge_router
from app.knowledge_store import KnowledgeStore
from app.local_files import router as local_files_router
from app.logical_relations import router as logical_relations_router
from app.model_config import ModelConfig, ModelStore, test_model
from app.prompts import router as prompts_router
from app.reconciliation import reconcile_runs
from app.reports import router as reports_router
from app.semantic_models import router as semantic_models_router
from app.sessions import router as sessions_router
from app.stream import router as stream_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = open_database(settings.database_url)
        try:
            await run_in_threadpool(migrate, engine)
            app.state.settings = settings
            app.state.stream_tasks = set()
            app.state.engine = engine
            app.state.models = ModelStore(engine)
            app.state.redis = redis.Redis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=2
            )
            settings.data_dir.mkdir(parents=True, exist_ok=True)
            app.state.knowledge = KnowledgeStore(engine, settings)
            async with AsyncSqliteSaver.from_conn_string(
                str(settings.data_dir / "checkpoints.sqlite")
            ) as saver:
                await saver.setup()
                app.state.saver = saver
                await reconcile_runs(app)
                await cleanup_jobs(app)

                async def retry_cleanup():
                    while True:
                        await asyncio.sleep(5)
                        await cleanup_jobs(app)

                cleanup_task = asyncio.create_task(retry_cleanup())
                try:
                    yield
                finally:
                    cleanup_task.cancel()
                    await asyncio.gather(cleanup_task, return_exceptions=True)
                    if app.state.stream_tasks:
                        await asyncio.gather(*list(app.state.stream_tasks), return_exceptions=True)
        finally:
            if hasattr(app.state, "redis"):
                app.state.redis.close()
            engine.dispose()

    app = FastAPI(title="DataAgent Python", lifespan=lifespan)
    app.include_router(agents_router)
    app.include_router(effective_config_router)
    app.include_router(datasources_router)
    app.include_router(logical_relations_router)
    app.include_router(bindings_router)
    app.include_router(prompts_router)
    app.include_router(sessions_router)
    app.include_router(deletion_router)
    app.include_router(history_router)
    app.include_router(reports_router)
    app.include_router(knowledge_router)
    app.include_router(local_files_router)
    app.include_router(semantic_models_router)
    app.include_router(stream_router)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    )

    def response(message: str, data=None, success: bool = True):
        return {"success": success, "message": message, "data": data}

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        # Do not return FastAPI's input-bearing detail array or credentials.
        fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in error.errors())
        return JSONResponse(response(f"参数校验失败: {fields}", success=False), status_code=400)

    @app.exception_handler(ValueError)
    async def business_error(request: Request, error: ValueError):
        return JSONResponse(response(str(error), success=False))

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception):
        return JSONResponse(
            response("服务暂不可用，请检查服务端存储状态", success=False), status_code=503
        )

    @app.get("/api/model-config/list")
    def models(request: Request):
        return response(
            "获取模型配置列表成功", [m.model_dump() for m in request.app.state.models.list()]
        )

    @app.post("/api/model-config/add")
    def add(config: ModelConfig, request: Request):
        request.app.state.models.add(config)
        return response("配置已保存")

    @app.put("/api/model-config/update")
    def update(config: ModelConfig, request: Request):
        request.app.state.models.update(config)
        return response("配置已更新")

    @app.delete("/api/model-config/{identifier}")
    def delete(identifier: int, request: Request):
        request.app.state.models.delete(identifier)
        return response("配置已删除")

    @app.post("/api/model-config/activate/{identifier}")
    def activate(identifier: int, request: Request):
        request.app.state.models.activate(identifier)
        return response("模型切换成功！")

    @app.post("/api/model-config/test/{identifier}")
    def connection_test(identifier: int, request: Request):
        test_model(
            request.app.state.models.read(identifier),
            settings.model_timeout,
            settings.embedding_dimension,
        )
        return response("连接测试成功！模型可用。")

    @app.get("/api/model-config/check-ready")
    def ready(request: Request):
        return response("模型配置检查完成", request.app.state.models.ready())

    @app.get("/echo/ok", response_class=PlainTextResponse)
    def health():
        return "ok"

    return app


app = create_app()
