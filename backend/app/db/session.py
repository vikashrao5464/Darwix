from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import ROOT
from app.db.models import Base
from app.db.migrations import migrate_initial_schema


def initialize_database(database_url: str):
    if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
        path = Path(database_url.removeprefix("sqlite:///"))
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        database_url = "sqlite:///" + path.as_posix()
    options = {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite") else {}
    if database_url == "sqlite:///:memory:":
        options["poolclass"] = StaticPool
    engine = create_engine(database_url, **options)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
    migrate_initial_schema(engine)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
