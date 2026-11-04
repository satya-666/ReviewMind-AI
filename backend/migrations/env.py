"""Apply versioned feedback schema migrations using environment settings."""
from alembic import context
from backend.app.settings import Settings
from backend.app.db import Base,Database
target_metadata=Base.metadata
settings=Settings.from_env().validate()
db=Database(settings.database_url)
with db.engine.connect() as connection:
    context.configure(connection=connection,target_metadata=target_metadata,render_as_batch=db.engine.dialect.name=='sqlite')
    with context.begin_transaction():context.run_migrations()
db.engine.dispose()
