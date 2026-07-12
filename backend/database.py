"""
database.py – SQLAlchemy engine + session factory
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Change to your MySQL credentials or use .env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:root@localhost:3306/kasi_flavour"
)

# FIX: PyMySQL does NOT accept "ssl_mode" as a connection parameter — that's
# a MySQLdb/mysqlclient-only option. Passing it via the URL query string
# (?ssl_mode=REQUIRED) causes:
#   TypeError: Connection.__init__() got an unexpected keyword argument 'ssl_mode'
# because SQLAlchemy forwards unknown URL query params straight through to
# PyMySQL's connect() as kwargs.
#
# PyMySQL instead expects SSL config via a "ssl" dict passed through
# connect_args. An empty dict enables TLS using a default SSL context
# (validated against the system CA trust store), which works for Aiven's
# publicly-trusted certificates without needing to download/reference a
# separate CA file.
#
# Only apply this for non-localhost connections — local MySQL during dev
# almost never has SSL configured, and forcing it would break local runs.
_connect_args = {}
if "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    _connect_args = {"ssl": {}}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency – yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()