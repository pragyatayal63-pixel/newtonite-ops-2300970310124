import os
import sys
import tempfile
import pathlib
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.scripts.seed import seed_database
import embedded_postgres

_pg_server = None
_test_db_url = None


@pytest.fixture(scope="session")
def postgres_engine():
    global _pg_server, _test_db_url
    temp_dir = pathlib.Path(tempfile.mkdtemp(prefix="newtonite_pg_"))
    _pg_server = embedded_postgres.PostgresServer(temp_dir)
    raw_uri = _pg_server.get_uri() # e.g. postgresql://postgres:@127.0.0.1:port/postgres
    # Convert uri to use psycopg driver
    _test_db_url = raw_uri.replace("postgresql://", "postgresql+psycopg://")
    
    engine = create_engine(_test_db_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    engine.dispose()
    if _pg_server:
        try:
            _pg_server.cleanup()
        except Exception:
            pass


@pytest.fixture(scope="function")
def db_session(postgres_engine):
    connection = postgres_engine.connect()
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = SessionTest()

    # Seed fresh demo data
    seed_database(session)

    yield session

    session.close()
    # Clean tables after each test
    with connection.begin():
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    connection.close()



@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    """Helper function to obtain bearer token headers for seeded demo users."""
    def _login(email: str, password: str = "Password123!"):
        res = client.post("/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return _login
