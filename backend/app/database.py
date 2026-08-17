from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

db_url = settings.sqlalchemy_database_url

# Optimized engine parameters for 512 MB RAM limit on Render free tier
engine_kwargs = {}
if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": 3,
        "max_overflow": 2,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_timeout": 10,  # Fail fast instead of hanging 30s
    })

engine = create_engine(db_url, **engine_kwargs)

# Set a statement timeout on PostgreSQL connections to kill runaway queries
if not db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_pg_timeout(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET statement_timeout = '15000'")  # 15 second max per query
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
