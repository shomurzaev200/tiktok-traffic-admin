from alembic import context
from app.db import engine, meta
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=meta)
    with context.begin_transaction():
        context.run_migrations()
