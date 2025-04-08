"""
Technician availability module.

This module currently provides a simplified, fixed availability schedule:
- Monday to Friday: 9:00 AM to 6:30 PM (9.5 hours)
- Saturday and Sunday: Unavailable

TODO: Replace with actual availability system that could include:
- Database-driven schedules
- External calendar integration
- PTO/vacation tracking
- Flexible work hours
- Break times
- Holidays
- Multiple shifts
"""

from datetime import datetime, time, timedelta, date
from typing import Optional
from calendar import day_name

from .models import DailyAvailability, Technician


# Default schedule configuration
DEFAULT_START_TIME = time(9, 0)  # 9:00 AM
DEFAULT_END_TIME = time(18, 30)  # 6:30 PM
DEFAULT_DURATION = timedelta(hours=9, minutes=30)  # 9.5 hours


def get_technician_availability(technician: Technician, day_number: int) -> Optional[DailyAvailability]:
    """
    Gets the availability for a given technician on a specific day.
    
    Currently implements a simplified fixed schedule:
    - Monday to Friday: 9:00 AM to 6:30 PM
    - Saturday and Sunday: Unavailable
    
    This is a placeholder implementation that will need to be replaced with a more
    sophisticated system that considers actual schedules, time off, etc.

    Args:
        technician (Technician): The technician to check availability for.
        day_number (int): The relative day number (1 = today, 2 = tomorrow, etc.).

    Returns:
        Optional[DailyAvailability]: The technician's availability for that day,
            or None if unavailable (weekends or beyond planning horizon).
    """
    if not 1 <= day_number <= 14:  # Only plan two weeks ahead
        return None

    # Calculate the target date
    target_date = date.today() + timedelta(days=day_number - 1)
    
    # Check if it's a weekend
    if target_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return None
    
    # Create datetime objects for start and end times
    start_datetime = datetime.combine(target_date, DEFAULT_START_TIME)
    end_datetime = datetime.combine(target_date, DEFAULT_END_TIME)
    
    return DailyAvailability(
        day_number=day_number,
        start_time=start_datetime,
        end_time=end_datetime,
        total_duration=DEFAULT_DURATION
    ) 