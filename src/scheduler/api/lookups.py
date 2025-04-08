from typing import Optional

from sqlalchemy.orm import Session, joinedload

from scheduler.db import models as db_models # Use db_models alias
from scheduler.models import ServiceCategory # Pydantic enum

def get_required_equipment(db: Session, service_id: int, ymm_id: int) -> Optional[str]:
    """
    Finds the required equipment model for a given service and YMM combination.

    Args:
        db: The SQLAlchemy database session.
        service_id: The ID of the service.
        ymm_id: The ID from the ymm_ref table.

    Returns:
        The required equipment model string if found, otherwise None.
    """

    # 1. Fetch the Service to determine its category
    service = db.query(db_models.Service).filter(db_models.Service.id == service_id).first()
    if not service:
        # Service not found
        return None

    # 2. Determine the correct equipment requirement table based on service category
    service_category: ServiceCategory = service.service_category
    requirement_model_class = None

    if service_category == ServiceCategory.ADAS:
        requirement_model_class = db_models.ADASEquipmentRequirement
    elif service_category == ServiceCategory.PROG:
        requirement_model_class = db_models.ProgEquipmentRequirement
    elif service_category == ServiceCategory.IMMO:
        requirement_model_class = db_models.ImmoEquipmentRequirement
    elif service_category == ServiceCategory.AIRBAG:
        requirement_model_class = db_models.AirbagEquipmentRequirement
    elif service_category == ServiceCategory.DIAG:
        requirement_model_class = db_models.DiagEquipmentRequirement
    else:
        return None

    # 3. Query the specific requirement table using ymm_id and service_id
    requirement = (
        db.query(requirement_model_class)
        .filter(
            requirement_model_class.ymm_id == ymm_id,
            requirement_model_class.service_id == service_id,
        )
        .first()
    )

    # 4. Return the equipment model if found
    if requirement:
        return requirement.equipment_model
    else:
        # No specific equipment requirement found for this service/YMM combo
        return None 