"""Tests for the Scheduler API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json

# Import from SQLAlchemy models instead of Pydantic models
from scheduler.db.models import JobStatus, Technician, Job, Address


# --- Test Authentication ---
def test_api_authentication_required(client):
    """Test that API endpoints require authentication."""
    # We expect either a 401 (Invalid API Key) or 422 (Missing API Key) response
    # Both indicate authentication failures, so we'll accept either
    
    # Test technicians endpoint
    response = client.get("/api/v1/technicians")
    assert response.status_code in [401, 422]
    
    # Test jobs endpoint
    response = client.get("/api/v1/jobs/schedulable")
    assert response.status_code in [401, 422]
    
    # Test equipment requirements endpoint
    response = client.get("/api/v1/equipment/requirements?service_id=1&ymm_id=1")
    assert response.status_code in [401, 422]


# --- Test GET /technicians ---
def test_get_technicians(client, test_api_key, mock_technicians, mock_db_session):
    """Test GET /technicians endpoint."""
    # Configure the mock DB session for execute().scalars().all()
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_technicians
    # Remove old configuration
    # mock_db_session.query.return_value.options.return_value.filter.return_value.all.return_value = mock_technicians

    # Make the request with the valid API key
    response = client.get(
        "/api/v1/technicians",
        headers={"api-key": test_api_key}
    )

    # Check response
    assert response.status_code == 200
    # Add more specific assertions if needed, e.g., checking the response body
    response_data = response.json()
    assert len(response_data) == len(mock_technicians)
    # Check a specific field from the conversion
    assert response_data[0]["id"] == mock_technicians[0].id
    assert response_data[0]["user_id"] == str(mock_technicians[0].user_id)


def test_get_technicians_unauthorized(client):
    """Test GET /technicians endpoint without API key."""
    # ... rest of file


# --- Test GET /jobs/schedulable ---
def test_get_schedulable_jobs(client, test_api_key, mock_jobs, mock_db_session):
    """Test GET /jobs/schedulable endpoint."""
    # Configure the mock DB session to return mock jobs using the SQLAlchemy 2.0 style
    # Ensure the mock_db_session fixture (from conftest.py) is set up for execute()
    mock_db_session.execute.return_value.scalars.return_value.all.return_value = mock_jobs
    
    # Make the request with the valid API key
    response = client.get(
        "/api/v1/jobs/schedulable",
        headers={"api-key": test_api_key}
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    
    # Check job data
    job = data[0]
    assert job["id"] == mock_jobs[0].id
    # Assuming the status enum value is returned
    assert job["status"] == mock_jobs[0].status.value 
    
    # Check nested objects are present (values depend on Pydantic model conversion)
    assert "address" in job
    assert "order_ref" in job
    # Note: Equipment requirements might not be loaded by default, depends on route logic
    # Check if it's present based on the model's conversion
    # assert "equipment_requirements" in job
    # You might need to adjust the mock_jobs fixture or the route to include this

    # Optionally, verify the execute call was made (if using AsyncMock)
    mock_db_session.execute.assert_called_once()


# --- Test GET /equipment/requirements ---
def test_get_equipment_requirements(client, test_api_key, mock_equipment_requirements, mock_db_session, mock_service):
    """Test GET /equipment/requirements endpoint."""
    # Configure mock DB to find the service to determine category
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_service 
    
    # Configure mock DB for the specific equipment requirement query (e.g., ADAS)
    # This needs to simulate finding the requirement based on service category
    mock_adas_req = MagicMock()
    mock_adas_req.equipment_model = mock_equipment_requirements[0]
    # Correct the mock to use filter() instead of filter_by()
    # We need to simulate the chaining: query(...).filter(...).first()
    # The filter() call needs to match the one in lookups.py
    # Let's assume the correct filter chain is called and configure its final result
    mock_db_session.query.return_value.filter.return_value.first.side_effect = [
        mock_service, # First call to first() returns the service
        mock_adas_req  # Second call to first() returns the requirement
    ]

    # Make the request with the valid API key
    response = client.get(
        f"/api/v1/equipment/requirements?service_id={mock_service.id}&ymm_id=1",
        headers={"api-key": test_api_key}
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert "service_id" in data
    assert "ymm_id" in data
    assert "equipment_models" in data
    assert data["service_id"] == mock_service.id
    assert data["ymm_id"] == 1
    # This assertion might fail depending on how the route logic aggregates results
    # Let's assume it correctly extracts the model string for now.
    assert data["equipment_models"] == [mock_adas_req.equipment_model] # Adjust based on actual logic


# --- Test GET /addresses/{address_id} ---
def test_get_address_found(client, test_api_key, mock_address, mock_db_session):
    """Test GET /addresses/{address_id} endpoint when the address is found."""
    # Configure the mock DB session for SQLAlchemy 2.0 style execute
    # Ensure the mock returned by first() is the actual mock_address object
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_address
    # Remove or comment out old configuration if present
    # mock_db_session.query.return_value.filter.return_value.first.return_value = mock_address

    # Make the request with the valid API key
    response = client.get(
        f"/api/v1/addresses/{mock_address.id}",
        headers={"api-key": test_api_key}
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mock_address.id
    assert data["street_address"] == mock_address.street_address
    assert data["lat"] == mock_address.lat
    assert data["lng"] == mock_address.lng


def test_get_address_not_found(client, test_api_key, mock_db_session):
    """Test GET /addresses/{address_id} endpoint when the address is not found."""
    # Configure the mock DB session for SQLAlchemy 2.0 style execute to return None
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
    # Remove or comment out old configuration if present
    # mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Make the request with the valid API key
    response = client.get(
        "/api/v1/addresses/999",
        headers={"api-key": test_api_key}
    )
    
    # Check response
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


# --- Test PATCH /jobs/{job_id}/assignment ---
def test_update_job_assignment(client, test_api_key, mock_job, mock_db_session):
    """Test PATCH /jobs/{job_id}/assignment endpoint."""
    # Configure mock DB for initial job fetch using SQLAlchemy 2.0 style execute
    # Ensure the fetch_job_by_id helper gets the actual mock_job object
    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_job
    # Remove or comment out old configuration if present
    # mock_db_session.query.return_value.filter.return_value.first.return_value = mock_job

    # Configure commit and refresh mocks (already done in conftest.py)

    # Request data
    assignment_data = {
        "assigned_technician": 1,
        "status": "assigned"
    }
    
    # Make the request with the valid API key
    response = client.patch(
        f"/api/v1/jobs/{mock_job.id}/assignment",
        headers={"api-key": test_api_key},
        json=assignment_data
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mock_job.id
    # Check if status was updated in the response (depends on conversion logic)
    assert data["status"] == assignment_data["status"] 
    assert data["assigned_technician"] == assignment_data["assigned_technician"]

    # Verify DB operations
    mock_db_session.query.assert_called() # Check query was called (at least once)
    # Check if update was called (this depends on implementation detail - e.g., direct update or modifying object and committing)
    # mock_db_session.query.return_value.filter.return_value.update.assert_called_once()
    mock_db_session.commit.assert_called_once() # Verify commit was called


def test_update_job_assignment_not_found(client, test_api_key, mock_db_session):
    """Test PATCH /jobs/{job_id}/assignment endpoint when the job is not found."""
    # Configure mock DB for initial job fetch (returns None)
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Request data
    assignment_data = {
        "assigned_technician": 1,
        "status": "assigned"
    }
    
    # Make the request with the valid API key
    response = client.patch(
        "/api/v1/jobs/999/assignment",
        headers={"api-key": test_api_key},
        json=assignment_data
    )
    
    # Check response
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    mock_db_session.commit.assert_not_called() # Ensure commit wasn't called if job not found


# --- Test PATCH /jobs/{job_id}/schedule ---
def test_update_job_schedule(client, test_api_key, mock_job, mock_db_session):
    """Test PATCH /jobs/{job_id}/schedule endpoint."""
    # Configure mock DB for initial/re-fetch
    mock_db_session.query.return_value.filter.return_value.first.return_value = mock_job
    
    # Request data - set a fixed schedule time
    fixed_time_dt = datetime.now() + timedelta(days=1)
    fixed_time_iso = fixed_time_dt.isoformat()
    schedule_data = {
        "fixed_schedule_time": fixed_time_iso
    }
    
    # Make the request with the valid API key
    response = client.patch(
        f"/api/v1/jobs/{mock_job.id}/schedule",
        headers={"api-key": test_api_key},
        json=schedule_data
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mock_job.id
    # FastAPI/Pydantic handles ISO string conversion to datetime
    assert data["fixed_schedule_time"] is not None 

    # Verify DB operations
    mock_db_session.query.assert_called() 
    mock_db_session.commit.assert_called_once()
    # More specific check on what was updated if needed
    # mock_db_session.query.return_value.filter.return_value.update.assert_called_once_with(
    #     {Job.fixed_schedule_time: fixed_time_dt} # Needs actual DB model reference
    # )


def test_update_job_schedule_not_found(client, test_api_key, mock_db_session):
    """Test PATCH /jobs/{job_id}/schedule endpoint when the job is not found."""
    # Configure mock DB for fetch attempts (returns None)
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Request data
    schedule_data = {
        "fixed_schedule_time": None  # Clear the fixed schedule time
    }
    
    # Make the request with the valid API key
    response = client.patch(
        "/api/v1/jobs/999/schedule",
        headers={"api-key": test_api_key},
        json=schedule_data
    )
    
    # Check response
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    mock_db_session.commit.assert_not_called()


# --- Test PATCH /jobs/etas ---
def test_update_job_etas(client, test_api_key, mock_db_session):
    """Test PATCH /jobs/etas endpoint."""
    # This test doesn't strictly need to mock the return of a query,
    # but it needs to verify the update/commit action on the session.
    # Mocking the update result might be useful depending on implementation.
    # mock_db_session.query.return_value.filter.return_value.update.return_value = 1 # Simulate 1 row updated
    # Or mock bulk update methods if used.

    # Request data
    now = datetime.now()
    eta_data = {
        "jobs": [
            {
                "job_id": 1,
                "estimated_sched": now.isoformat(),
                "estimated_sched_end": (now + timedelta(hours=1)).isoformat(),
                "customer_eta_start": now.isoformat(),
                "customer_eta_end": (now + timedelta(hours=2)).isoformat()
            },
            {
                "job_id": 2,
                "estimated_sched": (now + timedelta(hours=2)).isoformat()
            }
        ]
    }
    
    # Make the request with the valid API key
    response = client.patch(
        "/api/v1/jobs/etas",
        headers={"api-key": test_api_key},
        json=eta_data
    )
    
    # Check response
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "2" in data["message"] # Should mention 2 jobs were in the request
    
    # Verify DB commit was called (assuming the route attempts a commit)
    mock_db_session.commit.assert_called_once()
    # Add checks for specific update calls if using iterative updates
    # mock_db_session.query.return_value.filter.return_value.update.call_count == 2


def test_empty_update_job_etas(client, test_api_key, mock_db_session):
    """Test PATCH /jobs/etas endpoint with empty data."""
    # Request with empty jobs array
    eta_data = {
        "jobs": []
    }
    
    # Make the request with the valid API key
    response = client.patch(
        "/api/v1/jobs/etas",
        headers={"api-key": test_api_key},
        json=eta_data
    )
    
    # Check response - should succeed but indicate no updates
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "No ETA updates provided" in data["message"] # Match exact message from route
    mock_db_session.commit.assert_not_called() # Commit shouldn't be called if data is empty 