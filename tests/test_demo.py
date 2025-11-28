import pytest
import asyncio
import httpx
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import QUIZ_SECRET, LOGS_DIR
from main import app
from fastapi.testclient import TestClient

client = TestClient(app)

class TestSolveEndpoint:
    """Tests for /solve endpoint."""
    
    def test_malformed_json(self):
        """Test handling of malformed JSON."""
        response = client.post("/solve", data="not json", headers={"Content-Type": "application/json"})
        assert response.status_code == 422  # FastAPI validation error
    
    def test_missing_fields(self):
        """Test missing required fields."""
        response = client.post("/solve", json={"email": "test@test.com"})
        assert response.status_code == 422
    
    def test_wrong_secret(self):
        """Test wrong secret returns 403."""
        response = client.post("/solve", json={
            "email": "test@test.com",
            "secret": "wrong_secret",
            "url": "https://example.com"
        })
        assert response.status_code == 403
        assert "Invalid secret" in response.json()["detail"]
    
    def test_correct_secret_returns_200(self):
        """Test correct secret returns 200 with task_id."""
        response = client.post("/solve", json={
            "email": "test@test.com",
            "secret": QUIZ_SECRET,
            "url": "https://tds-llm-analysis.s-anand.net/demo"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert "task_id" in data
    
    def test_health_check(self):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

@pytest.mark.asyncio
async def test_demo_url_integration():
    """Integration test with actual demo URL."""
    # Note: This requires network access and the demo to be running
    demo_url = "https://tds-llm-analysis.s-anand.net/demo"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(demo_url, timeout=10)
            # Just verify the URL is accessible
            assert response.status_code == 200
        except Exception as e:
            pytest.skip(f"Demo URL not accessible: {e}")

def test_config_loads():
    """Test that config loads without errors."""
    from config import QUIZ_SECRET, TIMEOUT_SECONDS, MAX_FILE_SIZE_BYTES
    assert QUIZ_SECRET
    assert TIMEOUT_SECONDS > 0
    assert MAX_FILE_SIZE_BYTES > 0

def test_llm_helper_fallback():
    """Test LLM helper uses fallback heuristics."""
    from llm_helper import llm_helper
    
    # Test heuristic analysis
    analysis = llm_helper._heuristic_analyze("What is the sum of all values?", "")
    assert analysis["task_type"] == "sum"
    
    # Test heuristic solve with CSV data
    csv_data = "value\n10\n20\n30"
    answer = llm_helper._heuristic_solve("Sum the values", csv_data, "sum")
    assert answer == 60

def test_solver_time_enforcement():
    """Test that solver respects timeout."""
    from solver import QuizSolver
    import time
    
    solver = QuizSolver("test_task_id")
    # Test time expired check
    start = solver.start_time
    solver.start_time = time.time() - 200  # Set to 200 seconds ago
    
    # With TIMEOUT_SECONDS=180, should be expired
    assert solver._time_expired()