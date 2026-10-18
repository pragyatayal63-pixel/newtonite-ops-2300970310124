import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings

def test_project_sanity():
    assert True

@pytest.mark.asyncio
async def test_opspilot_app_metadata_and_health():
    assert "OpsPilot" in settings.PROJECT_NAME
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        health_res = await ac.get("/health")
        assert health_res.status_code == 200
        health_data = health_res.json()
        assert health_data["status"] == "ok"
        assert "OpsPilot" in health_data["app"]
