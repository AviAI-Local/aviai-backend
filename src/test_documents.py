import io
import pytest
from fastapi.testclient import TestClient

from main import app
from handlers.document_process import view

client = TestClient(app)


@pytest.mark.anyio
def test_extract_document_txt(monkeypatch):
    fake_txt = b"""
    PERSONAL CHARACTERISTICS
    Calm, decisive pilot.

    SCENARIO
    Emergency landing due to engine failure.
    Captain John Smith handled the situation.

    ATTITUDE IN THE INTERVIEW
    Confident and composed.
    """

    async def mock_process_document(file):
        return {
            "personal_characteristics": "Calm, decisive pilot.",
            "scenario": "Emergency landing due to engine failure.",
            "attitude_in_interview": "Confident and composed.",
            "usecase_name": "Emergency Landing",
            "usecase_summary": "A pilot performs an emergency landing after engine failure.",
            "character_name": "John Smith",
            "gender": "male",
        }

    # 🔑 PATCH THE VIEW MODULE, NOT THE SERVICE MODULE
    monkeypatch.setattr(
        view,
        "process_document",
        mock_process_document,
    )

    files = {
        "file": ("test.txt", io.BytesIO(fake_txt), "text/plain"),
    }

    response = client.post("/api/v1/document/extract", files=files)

    assert response.status_code == 200

    data = response.json()
    assert data["usecase_name"] == "Emergency Landing"
    assert data["character_name"] == "John Smith"
