from httpx import ASGITransport, AsyncClient

from app.core.settings import Settings
from tests.fakes import FakeEngine


async def test_health_returns_ok():
    from app.main import create_app

    app = create_app(Settings(_env_file=None), engine=FakeEngine())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
