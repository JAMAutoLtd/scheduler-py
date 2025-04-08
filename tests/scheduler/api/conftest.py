"""Shared fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from datetime import datetime, timedelta
import os

from scheduler.api.main import create_app
# Import from SQLAlchemy models instead of Pydantic models
from scheduler.db.models import (
    Address, Technician, Van, Equipment, Job, Order, Service, CustomerVehicle,
    CustomerType, JobStatus, ServiceCategory, EquipmentType
)

# Import the dependency to override
from scheduler.api.deps import get_api_key
from scheduler.db.database import get_db

# --- Mock Database Session Fixture ---
@pytest.fixture
def mock_db_session():
    """
    Provides a mock asynchronous database session (AsyncMock)
    compatible with execute().scalars().all().
    """
    # Use AsyncMock for the session
    db_session = AsyncMock(spec=Session) # spec=Session might need adjustment if using AsyncSession

    # Mock the execute method to be awaitable and return a result
    # that supports .scalars().all()
    mock_result = MagicMock() # Result itself doesn't need to be async
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [] # Default to empty list
    mock_result.scalars.return_value = mock_scalars
    
    # Configure execute to be an awaitable that returns the mock_result
    db_session.execute = AsyncMock(return_value=mock_result)

    # Mock commit and refresh as awaitable AsyncMocks
    db_session.commit = AsyncMock(return_value=None) # commit doesn't return anything significant
    db_session.refresh = AsyncMock(return_value=None) # refresh doesn't return anything significant

    # --- Keep old mock structure for compatibility if some tests still use query() ---
    # Make query().filter().first() chainable and return None by default
    db_session.query.return_value.filter.return_value.first.return_value = None
    # Make query().all() return an empty list by default
    db_session.query.return_value.all.return_value = []
    # Make query().options().filter()... chainable
    db_session.query.return_value.options.return_value.filter.return_value.first.return_value = None
    db_session.query.return_value.options.return_value.filter.return_value.all.return_value = []
    # --- End compatibility section ---

    yield db_session

# --- Test API Key Fixture ---
@pytest.fixture
def test_api_key():
    """Valid API key for testing."""
    return "test-api-key"

# --- Mock Settings Fixture ---
@pytest.fixture
def mock_settings(test_api_key):
    """Mock settings for API tests."""
    return {
        "database_url": "postgresql://user:password@localhost:5432/test_db",
        "api_keys": [test_api_key]
    }

# --- Test Client Fixture (Updated) ---
@pytest.fixture
def client(mock_settings, test_api_key, mock_db_session):
    """
    Create a FastAPI TestClient with mocked dependencies (settings and DB session).
    """
    # Set environment variable for tests (for settings dependency)
    os.environ["API_KEYS"] = test_api_key

    # Define a function that returns our mock session
    def override_get_db():
        yield mock_db_session
    
    # Mock the settings function and override the DB dependency
    with patch("scheduler.api.deps.get_settings", return_value=mock_settings):
        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as test_client:
            yield test_client
        
        # Clean up dependency overrides after tests
        app.dependency_overrides = {}


@pytest.fixture
def mock_address():
    """Create a mock address."""
    return Address(
        id=1,
        street_address="123 Test St",
        lat=40.7128,
        lng=-74.0060
    )


@pytest.fixture
def mock_equipment():
    """Create a mock equipment item."""
    return Equipment(
        id=1,
        equipment_type=EquipmentType.ADAS,
        model="AUTEL-CSC0602/01"
    )


@pytest.fixture
def mock_van(mock_equipment):
    """Create a mock van with equipment."""
    return Van(
        id=1,
        last_service=datetime.now() - timedelta(days=30),
        next_service=datetime.now() + timedelta(days=60),
        vin="1HGCM82633A004352",
        equipment=[mock_equipment]
    )


@pytest.fixture
def mock_technician(mock_address, mock_van):
    """Create a mock technician."""
    return Technician(
        id=1,
        user_id=uuid.uuid4(),
        assigned_van_id=mock_van.id,
        workload=2,
        home_address=mock_address,
        current_location=mock_address,
        assigned_van=mock_van
    )


@pytest.fixture
def mock_technicians(mock_technician):
    """Create a list of mock technicians."""
    return [mock_technician]


@pytest.fixture
def mock_vehicle():
    """Create a mock customer vehicle."""
    return CustomerVehicle(
        id=1,
        vin="1HGCM82633A004352",
        make="Honda",
        year=2022,
        model="Civic",
        ymm_id=1
    )


@pytest.fixture
def mock_service():
    """Create a mock service."""
    return Service(
        id=1,
        service_name="Front Radar Calibration",
        service_category=ServiceCategory.ADAS
    )


@pytest.fixture
def mock_order(mock_address, mock_vehicle, mock_service):
    """Create a mock order with attached related objects."""
    order = Order(
        id=1,
        user_id=uuid.uuid4(),
        vehicle_id=mock_vehicle.id,
        repair_order_number="RO12345",
        address_id=mock_address.id,
        earliest_available_time=datetime.now(),
        notes="Test notes",
        invoice=100001,
        customer_type=CustomerType.COMMERCIAL
    )
    # Manually attach related objects for the test
    order.address = mock_address
    order.vehicle = mock_vehicle
    order.services = [mock_service] # Simulate many-to-many relationship
    return order


@pytest.fixture
def mock_job(mock_address, mock_order):
    """Create a mock job with attached related objects."""
    job = Job(
        id=1,
        order_id=mock_order.id,
        service_id=1,
        assigned_technician_id=None,
        address_id=mock_address.id,
        priority=2,
        status=JobStatus.PENDING_REVIEW,
        requested_time=datetime.now(),
        estimated_sched=None,
        estimated_sched_end=None,
        customer_eta_start=None,
        customer_eta_end=None,
        job_duration=timedelta(minutes=90),
        notes="Test job notes",
        fixed_assignment=False,
        fixed_schedule_time=None
    )
    # Manually attach related objects for the test
    job.address = mock_address
    job.order = mock_order # Attach the enhanced mock_order
    
    # Simulate the equipment requirements relationship
    # Create mock JobEquipmentRequirement objects
    mock_req1 = MagicMock()
    mock_req1.equipment_model = "AUTEL-CSC0602/01"
    job.equipment_requirements_rel = [mock_req1] # Attach mock requirements
    
    return job


@pytest.fixture
def mock_jobs(mock_job):
    """Create a list of mock jobs."""
    return [mock_job]


@pytest.fixture
def mock_equipment_requirements():
    """Create mock equipment requirements."""
    return ["AUTEL-CSC0602/01", "AUTEL-CSC0602/02"] 