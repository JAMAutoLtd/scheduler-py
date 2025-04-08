# Changelog

All notable changes to this project will be documented in this file.

## [{today's date}]

### Added
- Created `CHANGELOG.md`.

### Changed
- **Refactoring (`src/scheduler/scheduler.py`):**
    - Extracted logic for calculating daily available time windows (considering fixed jobs) from `update_job_queues_and_routes` into a new helper function `_calculate_daily_available_windows`.
    - Updated `update_job_queues_and_routes` to use the new helper function.
    - Updated `calculate_eta` to use the new helper function, removing redundant logic.
    - Extracted logic for fitting dynamic units into available time windows from `update_job_queues_and_routes` into a new helper function `_fit_dynamic_units_into_windows`.
    - Extracted logic for combining, optimizing, and finalizing the daily schedule from `update_job_queues_and_routes` into a new helper function `_optimize_and_finalize_daily_schedule`.
    - Moved `calculate_daily_available_windows` and `fit_dynamic_units_into_windows` from `scheduler.py` to `utils.py` to improve modularity and resolve potential circular dependencies.
    - Updated imports and calls in `scheduler.py` accordingly.
    - **Reason:** To improve modularity, reduce code duplication, bring `scheduler.py` closer to the 500-line limit rule, and avoid circular dependencies.