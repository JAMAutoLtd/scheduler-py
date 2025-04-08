# tests/conftest.py
import os

# Set the TESTING environment variable before any tests are collected/run
os.environ["TESTING"] = "True"

# --- Your existing fixtures and test setup below ---
# Example:
# import pytest
# from fastapi.testclient import TestClient
# from src.scheduler.main import app # Assuming your FastAPI app instance is here
# ... other fixtures ...

# @pytest.fixture(scope="session")
# def test_client():
#     with TestClient(app) as client:
#         yield client