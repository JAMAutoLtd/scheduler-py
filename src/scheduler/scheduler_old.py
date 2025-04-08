# Import necessary modules
import requests
from datetime import datetime, timedelta, time
import math
from dateutil import parser

# Technician's current location and time
tech_current_location = input_data.get('technician_current_location', '').strip()
# Technician's home location
tech_home_location = input_data.get('technician_home_location', '').strip()
api_key = input_data.get('api_key', '').strip()

# Constants
JOB_DURATION = timedelta(minutes=90)
WORKDAY_START_TIME = time(9, 0)    # 9:00 AM
WORKDAY_END_TIME = time(18, 30)    # 6:30 PM
WORKDAYS = [0, 1, 2, 3, 4]         # Monday to Friday
HOME_UPDATE_START = time(20, 0)    # 8:00 PM
HOME_UPDATE_END = time(9, 0)       # 9:00 AM

# Function to determine TIME_ZONE_OFFSET based on date (handling daylight saving time)
def get_timezone_offset(date):
    # Assuming daylight saving time starts on the second Sunday in March
    # and ends on the first Sunday in November
    year = date.year
    # Daylight Saving Time starts on the second Sunday in March
    dst_start = datetime(year, 3, 8)
    while dst_start.weekday() != 6:  # 6 = Sunday
        dst_start += timedelta(days=1)
    # Daylight Saving Time ends on the first Sunday in November
    dst_end = datetime(year, 11, 1)
    while dst_end.weekday() != 6:
        dst_end += timedelta(days=1)
    if dst_start <= date.replace(tzinfo=None) < dst_end:
        return -6  # MDT (UTC-6)
    else:
        return -7  # MST (UTC-7)

# Define current_datetime before any function that uses it
TIME_ZONE_OFFSET = get_timezone_offset(datetime.utcnow())
current_utc_datetime = datetime.utcnow()
current_datetime = current_utc_datetime + timedelta(hours=TIME_ZONE_OFFSET)
current_date = current_datetime.date()
current_time = current_datetime.time()

# Enhanced Function to parse earliest_available_date
def parse_earliest_available_date(date_str):
    # List of supported date formats, including ISO 8601
    date_formats = [
        '%Y-%m-%d %H:%M:%S',        # e.g., "2024-10-17 09:00:00"
        '%Y-%m-%d %I:%M %p',        # e.g., "2024-10-17 09:00 AM"
        '%Y-%m-%d',                 # e.g., "2024-10-17"
        '%m/%d/%Y %I:%M %p',        # e.g., "10/17/2024 09:00 AM"
        '%m/%d/%Y %H:%M:%S',        # e.g., "10/17/2024 09:00:00"
        '%Y/%m/%d %I:%M %p',        # e.g., "2024/10/17 09:00 AM"
        '%Y/%m/%d %H:%M:%S',        # e.g., "2024/10/17 09:00:00"
        '%Y-%m-%dT%H:%M:%S.%fZ',     # e.g., "2024-10-26T03:00:00.000Z"
        '%Y-%m-%dT%H:%M:%SZ',        # e.g., "2024-10-26T03:00:00Z"
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            if fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d']:
                # Set default time to midnight if time component is missing
                parsed_date = datetime.combine(parsed_date.date(), time.min)
            return parsed_date
        except (ValueError, TypeError):
            continue
    # If all parsing attempts fail, try using dateutil's parser
    try:
        parsed_date = parser.isoparse(date_str)
        return parsed_date
    except (ValueError, TypeError):
        pass
    # If still failing, return current_datetime to allow immediate scheduling
    print(f"Warning: Unable to parse earliest_available_date '{date_str}'. Using current datetime.")
    return current_datetime

# Function to assign numerical values to priorities
def priority_value(priority):
    # Assuming priority strings are like 'p1', 'p2', etc.
    if priority.startswith('p') and priority[1:].isdigit():
        return int(priority[1:])
    else:
        return 5  # Default priority if not specified correctly

# Function to map input priority to Todoist priority
def map_priority_todoist(priority_str):
    mapping = {
        'p1': '4',  # Highest priority
        'p2': '3',
        'p3': '2',
        'p4': '1',  # Lowest priority
    }
    return mapping.get(priority_str.lower(), '1')  # Default to '1' if not mapped

# Function to reintroduce commas in addresses
def reintroduce_commas(address):
    address = address.replace(' Calgary', ', Calgary')
    address = address.replace(' AB', ', AB')
    address = address.replace(' Canada', ', Canada')
    return address

# Function to geocode address
def geocode_address(address):
    try:
        geocode_url = 'https://maps.googleapis.com/maps/api/geocode/json'
        address = reintroduce_commas(address)
        params = {
            'address': address,
            'key': api_key
        }
        response = requests.get(geocode_url, params=params).json()
        if response['status'] == 'OK':
            location = response['results'][0]['geometry']['location']
            return f"{location['lat']},{location['lng']}"
        else:
            print(f"Failed to geocode address: {address}")
            print(f"Geocoding API response: {response}")
            return None
    except Exception as e:
        print(f"Exception during geocoding: {e}")
        return None

# Function to calculate straight-line distance between two coordinates using the Haversine formula
def calculate_distance(origin, destination):
    lat1, lon1 = map(float, origin.split(','))
    lat2, lon2 = map(float, destination.split(','))
    R = 6371  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c  # in kilometers
    return distance

# Function to get travel time using Distance Matrix API
def get_travel_time(origin, destination, departure_time):
    try:
        # Convert local departure_time to UTC by subtracting TIME_ZONE_OFFSET
        departure_time_utc = departure_time - timedelta(hours=TIME_ZONE_OFFSET)
        # Calculate Unix timestamp
        departure_time_unix = int(departure_time_utc.timestamp())
        # Ensure departure_time is in the future by adding a buffer if necessary
        current_unix_time = int(datetime.utcnow().timestamp())
        if departure_time_unix < current_unix_time:
            departure_time_unix = current_unix_time + 300  # Add 5 minutes buffer

        print(f"Local departure time: {departure_time}")
        print(f"UTC departure time: {departure_time_utc}")
        print(f"Departure time Unix timestamp: {departure_time_unix}")
        print(f"Current Unix time: {current_unix_time}")

        distance_matrix_url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'origins': origin,
            'destinations': destination,
            'key': api_key,
            'mode': 'driving',
            'units': 'metric',
            'departure_time': departure_time_unix,
        }
        response = requests.get(distance_matrix_url, params=params)
        data = response.json()
        if data['status'] == 'OK':
            element = data['rows'][0]['elements'][0]
            if element['status'] == 'OK':
                duration = element.get('duration_in_traffic', element['duration'])['value']  # in seconds
                return duration
            else:
                print(f"Element status not OK: {element['status']}")
                return None
        else:
            print(f"Distance Matrix API error: {data['status']}")
            print(f"API response: {data}")
            return None
    except Exception as e:
        print(f"Exception during travel time calculation: {e}")
        return None

# Function to check if a date is a workday
def is_workday(date):
    return date.weekday() in WORKDAYS

# Function to get the next workday
def get_next_workday(date):
    next_day = date + timedelta(days=1)
    while not is_workday(next_day):
        next_day += timedelta(days=1)
    return next_day

# Function to reorder jobs based on the Nearest Neighbor Heuristic
def reorder_jobs_nearest_neighbor(jobs, start_location):
    if not jobs:
        return []
    
    reordered = []
    current_loc = start_location
    remaining_jobs = jobs.copy()
    
    while remaining_jobs:
        # Find the closest job to the current location
        closest_job = min(remaining_jobs, key=lambda job: calculate_distance(current_loc, job['location']))
        reordered.append(closest_job)
        current_loc = closest_job['location']
        remaining_jobs.remove(closest_job)
    
    return reordered

def schedule_jobs(jobs):
    scheduled_jobs = []
    
    # Group jobs by priority
    priority_groups = {}
    for job in jobs:
        prio = job['priority_value']
        if prio not in priority_groups:
            priority_groups[prio] = []
        priority_groups[prio].append(job)
    
    # Sort priorities ascending (lower number = higher priority)
    sorted_priorities = sorted(priority_groups.keys())
    
    # Initialize scheduling day and time
    if is_workday(current_date):
        scheduling_day = current_date
        scheduling_time = current_datetime
    else:
        scheduling_day = get_next_workday(current_date)
        scheduling_time = datetime.combine(scheduling_day, WORKDAY_START_TIME)
        print(f"Initial scheduling day {current_date} is not a workday. Setting to next workday {scheduling_day}.")
    
    # Determine starting location
    if is_workday(current_date):
        if (current_time >= HOME_UPDATE_START) or (current_time < WORKDAY_START_TIME):
            scheduling_location = tech_home_location
            print("Scheduler is running outside work hours. Setting current location to home location.")
        else:
            scheduling_location = tech_current_location
            print("Scheduler is running during work hours. Using technician's current location.")
    else:
        scheduling_location = tech_home_location
        print("Scheduling starts on a non-current day. Setting location to home location.")
    
    while True:
        if not is_workday(scheduling_day):
            scheduling_day = get_next_workday(scheduling_day)
            scheduling_time = datetime.combine(scheduling_day, WORKDAY_START_TIME)
            scheduling_location = tech_home_location
            print(f"Skipping non-workday {scheduling_day}.")
            continue

        print(f"\nScheduling for {scheduling_day} ({scheduling_day.strftime('%A')})")
        print(f"Starting at {scheduling_time.time()} from location {scheduling_location}")

        # Initialize day's schedule
        day_jobs = []
        current_dt = scheduling_time
        current_loc = scheduling_location

        # Collect available jobs for the day, grouped by priority
        available_jobs = []
        for prio in sorted_priorities:
            group_jobs = priority_groups.get(prio, [])
            # Filter jobs whose earliest_available_date <= scheduling_day
            eligible_jobs = [job for job in group_jobs if job['earliest_available_date'].date() <= scheduling_day]
            available_jobs.extend(eligible_jobs)
        
        # Process jobs starting from highest priority
        for prio in sorted_priorities:
            group_jobs = [job for job in available_jobs if job['priority_value'] == prio]
            if not group_jobs:
                continue
            # Reorder group_jobs based on proximity
            reordered_group = reorder_jobs_nearest_neighbor(group_jobs, current_loc)
            for job in reordered_group:
                # Calculate travel time from current location
                origin = current_loc
                departure_time = current_dt
                travel_time_seconds = get_travel_time(origin, job['location'], departure_time)
                if travel_time_seconds is None:
                    print(f"Skipping job {job['task_id']} due to travel time calculation failure.")
                    continue  # Skip this job
                
                travel_time = timedelta(seconds=travel_time_seconds)
                arrival_time = departure_time + travel_time
                # Adjust arrival_time based on earliest_available_date
                arrival_time = max(arrival_time, job['earliest_available_date'])
                
                # Ensure arrival_time is within work hours
                if arrival_time.time() < WORKDAY_START_TIME:
                    arrival_time = datetime.combine(arrival_time.date(), WORKDAY_START_TIME)
                elif arrival_time.time() > WORKDAY_END_TIME:
                    print(f"Cannot schedule job {job['task_id']} on {scheduling_day} as arrival time {arrival_time.time()} is after work hours.")
                    continue  # Skip this job
                
                end_time = arrival_time + JOB_DURATION
                # Ensure job ends within work hours
                if end_time.time() > WORKDAY_END_TIME:
                    print(f"Cannot schedule job {job['task_id']} as it would end at {end_time.time()}, after work hours.")
                    continue  # Skip this job
                
                # Check if the job fits into the available time
                if end_time > datetime.combine(scheduling_day, WORKDAY_END_TIME):
                    print(f"Cannot schedule job {job['task_id']} as it exceeds workday end time.")
                    continue  # Skip this job
                
                # Schedule the job
                scheduled_job = {
                    'task_id': job['task_id'],
                    'submission_id': job['submission_id'],
                    'start_datetime': arrival_time,
                    'end_datetime': end_time,
                    'address': job['address'],
                    'todoist_title': job['todoist_title'],
                    'optimized_todoist_title': job['todoist_title'],
                    'old_start_date': job['old_start_date'],
                    'earliest_available_date': job['earliest_available_date'],
                    'priority': job['priority'],  # Original priority string (e.g., 'p1')
                    'todoist_priority': map_priority_todoist(job['priority']),  # Mapped Todoist priority
                }
                day_jobs.append(scheduled_job)
                print(f"Scheduled job {job['task_id']} at {arrival_time.time()} on {scheduling_day}")
                
                # Update scheduling_time and current_loc for next job
                current_dt = end_time
                current_loc = job['location']
                
                # Remove job from priority_groups and available_jobs
                priority_groups[prio].remove(job)
                available_jobs.remove(job)
        
        # Add day's jobs to scheduled_jobs
        scheduled_jobs.extend(day_jobs)
        
        # Determine if there are more jobs to schedule
        remaining_jobs = any(priority_groups[prio] for prio in sorted_priorities)
        if not remaining_jobs:
            break  # All jobs have been scheduled
        
        # Move to next workday
        scheduling_day = get_next_workday(scheduling_day)
        scheduling_time = datetime.combine(scheduling_day, WORKDAY_START_TIME)
        scheduling_location = tech_home_location  # Start next day from home

    return scheduled_jobs

# Step 1: Prepare Job Data
jobs = []
# Retrieve all input data
task_ids = input_data.get('task_ids', '').split(',')
priorities = input_data.get('priorities', '').split(',')
addresses = input_data.get('addresses', '').split(',')
submission_ids = input_data.get('submission_ids', '').split(',')
todoist_titles = input_data.get('todoist_titles', '').split(',')
old_start_dates = input_data.get('old_start_dates', '').split(',')
earliest_available_dates = input_data.get('earliest_available_dates', '').split(',')

num_jobs = len(task_ids)

# Validation: Ensure that input lists have at least as many elements as task_ids
min_length = min(len(priorities), len(addresses), len(submission_ids), len(todoist_titles), len(old_start_dates), len(earliest_available_dates))
if min_length < num_jobs:
    print("Warning: Some input lists have fewer elements than 'task_ids'. Missing entries will be set to default values.")

for i in range(num_jobs):
    address = addresses[i].strip() if i < len(addresses) else ''
    location = geocode_address(address) if address else None
    if location:
        print(f"Geocoded address: {address} to location: {location}")
        old_start_date = old_start_dates[i].strip() if i < len(old_start_dates) else ''
        earliest_available_date_str = earliest_available_dates[i].strip() if i < len(earliest_available_dates) else ''
        earliest_available_date = parse_earliest_available_date(earliest_available_date_str)
        jobs.append({
            'task_id': task_ids[i].strip() if i < len(task_ids) else '',
            'priority': priorities[i].strip() if i < len(priorities) else '',
            'priority_value': priority_value(priorities[i].strip()) if i < len(priorities) else 5,
            'address': address,
            'location': location,
            'submission_id': submission_ids[i].strip() if i < len(submission_ids) else '',
            'todoist_title': todoist_titles[i].strip() if i < len(todoist_titles) else '',
            'old_start_date': old_start_date,  # Existing Field
            'earliest_available_date': earliest_available_date,  # New Field
        })
    else:
        print(f"Skipping job due to geocoding failure: {address}")

# Validate that all jobs have 'location'
valid_jobs = []
for job in jobs:
    if 'location' in job and job['location']:
        valid_jobs.append(job)
    else:
        print(f"Warning: Job {job.get('task_id', 'Unknown')} is missing 'location'. Skipping this job.")

# Step 2: Schedule Jobs Based on Priority, Proximity, and Earliest Available Date
scheduled_jobs = schedule_jobs(valid_jobs)

# Prepare Outputs
output_task_ids = []
output_submission_ids = []
output_start_datetimes = []
output_queue_numbers = []
output_addresses = []
output_todoist_titles = []  # Original Titles
output_optimized_todoist_titles = []  # Optimized Titles
output_old_start_dates = []  # Existing Output
output_earliest_available_dates = []  # New Output
output_priorities = []  # New Output: Todoist Priorities

# Sort scheduled jobs by start datetime
scheduled_jobs.sort(key=lambda x: x['start_datetime'])

for idx, job in enumerate(scheduled_jobs):
    output_task_ids.append(job['task_id'])
    output_submission_ids.append(job['submission_id'])
    formatted_datetime = job['start_datetime'].strftime('%Y-%m-%d %H:%M')  # Reverted to original format
    output_start_datetimes.append(formatted_datetime)
    output_queue_numbers.append(str(idx + 1))
    output_addresses.append(job['address'])
    output_todoist_titles.append(job['todoist_title'])  # Original todoist_title
    output_optimized_todoist_titles.append(job['optimized_todoist_title'])  # New output
    output_old_start_dates.append(job['old_start_date'])  # Existing Output
    output_earliest_available_dates.append(job['earliest_available_date'].strftime('%Y-%m-%d %H:%M:%S'))  # New Output
    output_priorities.append(job['todoist_priority'])  # New Output: Todoist Priority

# Return the outputs
return {
    'optimized_task_ids': output_task_ids,
    'optimized_submission_ids': output_submission_ids,
    'optimized_start_datetimes': output_start_datetimes,
    'optimized_queue_numbers': output_queue_numbers,
    'optimized_addresses': output_addresses,
    'todoist_titles': output_todoist_titles,  # Include original titles if needed
    'optimized_todoist_titles': output_optimized_todoist_titles,  # New output
    'old_start_dates': output_old_start_dates,  # Existing Output
    'earliest_available_dates': output_earliest_available_dates,  # New Output
    'optimized_priorities': output_priorities,  # New Output: Todoist Priorities
}
