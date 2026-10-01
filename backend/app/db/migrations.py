from sqlalchemy import inspect, text


def migrate_initial_schema(engine):
    """Non-destructive Phase 0 -> Phase 2 SQLite migration."""
    if engine.dialect.name != "sqlite":
        return
    inspector = inspect(engine)
    if "calls" in inspector.get_table_names() and "revision" not in {c["name"] for c in inspector.get_columns("calls")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE calls ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"))
