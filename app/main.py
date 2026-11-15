"""FastAPI 主应用:API 路由 + 前端静态页托管。

启动: py -I scripts\run_server.py  或  uvicorn app.main:app
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import ROOT_DIR
from app.db.session import init_db

WEB_DIR = ROOT_DIR / "web"

app = FastAPI(title="合理用药知识审查平台", version="1.0.0")
app.include_router(router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


# 静态资源(js/css),挂在 /static
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
