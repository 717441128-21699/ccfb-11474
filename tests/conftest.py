"""pytest 全局夹具:把数据库重定向到临时目录,避免污染正式库。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def isolated_db(tmp_path_factory):
    tmp_db_dir = tmp_path_factory.mktemp("test_db")
    # 在导入 app 配置后覆盖数据库路径
    import app.config as config
    import app.db.session as dbsession

    db_file = tmp_db_dir / "test.sqlite3"
    config.DATABASE_URL = f"sqlite:///{db_file.as_posix()}"
    config.DB_PATH = db_file
    # 重建 engine
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    dbsession.engine = create_engine(
        config.DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
    dbsession.SessionLocal = sessionmaker(
        bind=dbsession.engine, autoflush=False, expire_on_commit=False)
    dbsession.init_db()
    yield
