import { Technician, Job, TechnicianAvailability } from '../types/database.types';

// Define standard work hours in UTC
export const WORK_START_HOUR_UTC = 9; // 9:00 AM UTC
export const WORK_END_HOUR_UTC = 18; // 6:00 PM UTC
export const WORK_END_MINUTE_UTC = 30; // 6:30 PM UTC

/**
 * Calculates the current time adjusted to be within today's UTC work window.
 * If before start time, returns start time. If after end time, returns end time.
 * Only considers M-F in UTC.
 * @returns {Date} The adjusted current UTC time.
 */
function getAdjustedCurrentTimeUTC(): Date {
    const now = new Date(); // Current time

    // Get UTC day: 0 (Sun) - 6 (Sat)
    const dayOfWeekUTC = now.getUTCDay(); 

    // Create Date objects for start/end representing UTC times
    const startOfDayUTC = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), WORK_START_HOUR_UTC, 0, 0, 0));
    const endOfDayUTC = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), WORK_END_HOUR_UTC, WORK_END_MINUTE_UTC, 0, 0));

    // If outside working days (Sat/Sun UTC) or after work hours UTC, consider end of day (effectively unavailable)
    if (dayOfWeekUTC === 0 || dayOfWeekUTC === 6 || now.getTime() > endOfDayUTC.getTime()) {
        return endOfDayUTC;
    }

    // If before work hours start UTC, use the start time UTC
    if (now.getTime() < startOfDayUTC.getTime()) {
        return startOfDayUTC;
    }

    // Otherwise, we are within the UTC workday
    return now;
}

/**
 * Calculates the earliest availability for each technician based on locked jobs and work hours (UTC).
 * Updates the `earliest_availability` and `current_location` properties of the technician objects in place.
 *
 * @param {Technician[]} technicians - Array of technician objects.
 * @param {Job[]} lockedJobs - Array of jobs with status 'en_route', 'in_progress', or 'fixed_time'.
 */
export function calculateTechnicianAvailability(
  technicians: Technician[],
  lockedJobs: Job[],
): void {
  console.log(`Calculating availability (UTC) for ${technicians.length} technicians based on ${lockedJobs.length} locked jobs...`);

  const currentTimeUTC = getAdjustedCurrentTimeUTC(); 
  // Calculate end of workday in UTC based on the current UTC time
  const endOfWorkDayUTC = new Date(Date.UTC(currentTimeUTC.getUTCFullYear(), currentTimeUTC.getUTCMonth(), currentTimeUTC.getUTCDate(), WORK_END_HOUR_UTC, WORK_END_MINUTE_UTC, 0, 0));

  const lockedJobsByTechnician = new Map<number, Job[]>();
  for (const job of lockedJobs) {
    if (job.assigned_technician !== null) {
      if (!lockedJobsByTechnician.has(job.assigned_technician)) {
        lockedJobsByTechnician.set(job.assigned_technician, []);
      }
      lockedJobsByTechnician.get(job.assigned_technician)?.push(job);
    }
  }

  for (const tech of technicians) {
    // Start with adjusted current UTC time
    let techEarliestAvailableUTC = new Date(currentTimeUTC.getTime()); 
    let lastJobLocation: { lat: number; lng: number } | undefined = tech.current_location; // Start with van location if available

    const techLockedJobs = lockedJobsByTechnician.get(tech.id) || [];

    // Sort jobs by estimated start/end time to process chronologically
    techLockedJobs.sort((a, b) => {
        // Ensure comparison treats times as UTC
        const timeA = a.fixed_schedule_time || a.estimated_sched || '0';
        const timeB = b.fixed_schedule_time || b.estimated_sched || '0';
        // new Date() parsing ISO strings correctly gives UTC time value
        return new Date(timeA).getTime() - new Date(timeB).getTime(); 
    });

    for (const job of techLockedJobs) {
      let jobStartTimeUTC: Date | null = null;
      let jobEndTimeUTC: Date | null = null;

      // Dates are parsed from ISO strings (assumed UTC)
      if (job.status === 'fixed_time' && job.fixed_schedule_time) {
        jobStartTimeUTC = new Date(job.fixed_schedule_time);
        // Estimate end time based on duration (add milliseconds)
        jobEndTimeUTC = new Date(jobStartTimeUTC.getTime() + job.job_duration * 60000);
      } else if ((job.status === 'en_route' || job.status === 'in_progress') && job.estimated_sched) {
        jobStartTimeUTC = new Date(job.estimated_sched);
        // Calculate end time by adding duration milliseconds
        jobEndTimeUTC = new Date(jobStartTimeUTC.getTime() + job.job_duration * 60000);
      }
      
      // Compare job end time (UTC) with tech's current earliest availability (UTC)
      if (jobEndTimeUTC && jobEndTimeUTC.getTime() > techEarliestAvailableUTC.getTime()) {
        techEarliestAvailableUTC = jobEndTimeUTC;
        // Update technician's location to this job's address if available
        if (job.address?.lat && job.address?.lng) {
            lastJobLocation = { lat: job.address.lat, lng: job.address.lng };
        }
      }
    }

    // Ensure availability is not beyond the end of the UTC workday
    if (techEarliestAvailableUTC.getTime() > endOfWorkDayUTC.getTime()) {
        techEarliestAvailableUTC = endOfWorkDayUTC;
    }

    // Update the technician object with ISO string (which is inherently UTC)
    tech.earliest_availability = techEarliestAvailableUTC.toISOString();
    tech.current_location = lastJobLocation; // Update location based on last locked job

    console.log(`Technician ${tech.id}: Available from ${tech.earliest_availability} (UTC) at ${lastJobLocation ? `(${lastJobLocation.lat}, ${lastJobLocation.lng})` : 'default location'}`);
  }
}

/**
 * Calculates the earliest availability for each technician for a specific target day (UTC),
 * based on standard work hours (Mon-Fri UTC, 9:00 AM - 6:30 PM UTC) and their home location.
 * Does not consider currently locked jobs as it's for future planning.
 *
 * @param {Technician[]} technicians - Array of technician objects, must include `home_location`.
 * @param {Date} targetDate - The specific date for which to calculate availability (time part is ignored, only date part is used for UTC calculations).
 * @returns {TechnicianAvailability[]} An array of availability details for technicians available on the target day.
 */
export function calculateAvailabilityForDay(
  technicians: Technician[],
  targetDate: Date,
): TechnicianAvailability[] {
  // Extract UTC date components
  const targetYearUTC = targetDate.getUTCFullYear();
  const targetMonthUTC = targetDate.getUTCMonth();
  const targetDayOfMonthUTC = targetDate.getUTCDate();
  const targetDayOfWeekUTC = targetDate.getUTCDay(); // 0 (Sun) - 6 (Sat)
  const targetDateStr = `${targetYearUTC}-${(targetMonthUTC + 1).toString().padStart(2, '0')}-${targetDayOfMonthUTC.toString().padStart(2, '0')}`;

  console.log(`Calculating availability (UTC) for ${technicians.length} technicians for date: ${targetDateStr}`);
  const availabilityResults: TechnicianAvailability[] = [];

  // Skip calculation if the target date is a weekend (UTC)
  if (targetDayOfWeekUTC === 0 || targetDayOfWeekUTC === 6) {
    console.log(`Target date ${targetDateStr} is a weekend (UTC). No availability calculated.`);
    // Holiday checking is handled by upstream availability data, not explicitly here.
    return availabilityResults; // Return empty array for non-working days
  }

  // Create Date objects representing UTC start/end times for the target day
  const startOfWorkDayUTC = new Date(Date.UTC(targetYearUTC, targetMonthUTC, targetDayOfMonthUTC, WORK_START_HOUR_UTC, 0, 0, 0));
  const endOfWorkDayUTC = new Date(Date.UTC(targetYearUTC, targetMonthUTC, targetDayOfMonthUTC, WORK_END_HOUR_UTC, WORK_END_MINUTE_UTC, 0, 0));

  for (const tech of technicians) {
    // Ensure the technician has a valid home location defined
    if (!tech.home_location || typeof tech.home_location.lat !== 'number' || typeof tech.home_location.lng !== 'number') {
      console.warn(`Technician ${tech.id} skipped: Missing or invalid home_location.`);
      continue; // Skip technician if home location is missing or invalid
    }

    // Create the availability object for this technician on this day
    const techAvailability: TechnicianAvailability = {
      technicianId: tech.id,
      availabilityStartTimeISO: startOfWorkDayUTC.toISOString(),
      availabilityEndTimeISO: endOfWorkDayUTC.toISOString(),
      startLocation: tech.home_location, // Use home location as the starting point
    };

    availabilityResults.push(techAvailability);
    console.log(`Technician ${tech.id}: Available on ${targetDateStr} from ${techAvailability.availabilityStartTimeISO} to ${techAvailability.availabilityEndTimeISO} (UTC) starting at home (${tech.home_location.lat}, ${tech.home_location.lng})`);
  }

  console.log(`Found ${availabilityResults.length} technicians available for ${targetDateStr} (UTC).`);
  return availabilityResults;
}

// Example usage might require fetching technicians and locked jobs first
/*
import { getActiveTechnicians } from '../supabase/technicians';
import { getRelevantJobs } from '../supabase/jobs';

async function runAvailabilityExample() {
  try {
    const technicians = await getActiveTechnicians();
    const allJobs = await getRelevantJobs();
    const lockedJobs = allJobs.filter(job => 
        job.status === 'en_route' || job.status === 'in_progress' || job.status === 'fixed_time'
    );

    calculateTechnicianAvailability(technicians, lockedJobs);

    console.log('\nTechnician availability updated:');
    console.log(JSON.stringify(technicians, null, 2));

  } catch (err) {
    console.error('Failed to run availability example:', err);
  }
}

// runAvailabilityExample();
*/ 