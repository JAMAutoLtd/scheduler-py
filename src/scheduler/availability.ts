import { Technician, Job } from '../types/database.types';

// Define standard work hours (adjust as needed)
const WORK_START_HOUR = 9; // 9:00 AM
const WORK_END_HOUR = 18; // 6:00 PM
const WORK_END_MINUTE = 30; // 6:30 PM

/**
 * Calculates the current time adjusted to be within today's work window.
 * If before start time, returns start time. If after end time, returns end time.
 * Only considers M-F.
 * @returns {Date} The adjusted current time.
 */
function getAdjustedCurrentTime(): Date {
    const now = new Date();
    const dayOfWeek = now.getDay(); // 0 (Sun) - 6 (Sat)

    const startOfDay = new Date(now); // Copy date part
    startOfDay.setHours(WORK_START_HOUR, 0, 0, 0); 

    const endOfDay = new Date(now);
    endOfDay.setHours(WORK_END_HOUR, WORK_END_MINUTE, 0, 0);

    // If outside working days (Sat/Sun) or after work hours, consider end of day (effectively unavailable)
    if (dayOfWeek === 0 || dayOfWeek === 6 || now > endOfDay) {
        return endOfDay;
    }

    // If before work hours start, use the start time
    if (now < startOfDay) {
        return startOfDay;
    }

    // Otherwise, we are within the workday
    return now;
}

/**
 * Calculates the earliest availability for each technician based on locked jobs and work hours.
 * Updates the `earliest_availability` and `current_location` properties of the technician objects in place.
 *
 * @param {Technician[]} technicians - Array of technician objects.
 * @param {Job[]} lockedJobs - Array of jobs with status 'en_route', 'in_progress', or 'fixed_time'.
 */
export function calculateTechnicianAvailability(
  technicians: Technician[],
  lockedJobs: Job[],
): void {
  console.log(`Calculating availability for ${technicians.length} technicians based on ${lockedJobs.length} locked jobs...`);

  const currentTime = getAdjustedCurrentTime(); 
  const endOfWorkDay = new Date(currentTime);
  endOfWorkDay.setHours(WORK_END_HOUR, WORK_END_MINUTE, 0, 0);

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
    let techEarliestAvailable = new Date(currentTime); // Start with adjusted current time
    let lastJobLocation: { lat: number; lng: number } | undefined = tech.current_location; // Start with van location if available

    const techLockedJobs = lockedJobsByTechnician.get(tech.id) || [];

    // Sort jobs by estimated start/end time to process chronologically
    techLockedJobs.sort((a, b) => {
        const timeA = a.fixed_schedule_time || a.estimated_sched || '0';
        const timeB = b.fixed_schedule_time || b.estimated_sched || '0';
        return new Date(timeA).getTime() - new Date(timeB).getTime();
    });

    for (const job of techLockedJobs) {
      let jobStartTime: Date | null = null;
      let jobEndTime: Date | null = null;

      if (job.status === 'fixed_time' && job.fixed_schedule_time) {
        jobStartTime = new Date(job.fixed_schedule_time);
        // Estimate end time based on duration, assume duration is in minutes
        jobEndTime = new Date(jobStartTime.getTime() + job.job_duration * 60000);
      } else if ((job.status === 'en_route' || job.status === 'in_progress') && job.estimated_sched) {
        // For ongoing jobs, assume they started at estimated_sched 
        // and calculate estimated end based on duration.
        // More accurate logic might use real-time progress if available.
        jobStartTime = new Date(job.estimated_sched);
        jobEndTime = new Date(jobStartTime);
        jobEndTime.setMinutes(jobStartTime.getMinutes() + job.job_duration);
      }
      
      // If the job ends after the tech's current earliest availability,
      // update the availability to the job's end time.
      if (jobEndTime && jobEndTime > techEarliestAvailable) {
        techEarliestAvailable = jobEndTime;
        // Update technician's location to this job's address if available
        if (job.address?.lat && job.address?.lng) {
            lastJobLocation = { lat: job.address.lat, lng: job.address.lng };
        }
      }
    }

    // Ensure availability is not beyond the end of the workday
    if (techEarliestAvailable > endOfWorkDay) {
        techEarliestAvailable = endOfWorkDay;
    }

    // Update the technician object
    tech.earliest_availability = techEarliestAvailable.toISOString();
    tech.current_location = lastJobLocation; // Update location based on last locked job

    console.log(`Technician ${tech.id}: Available from ${tech.earliest_availability} at ${lastJobLocation ? `(${lastJobLocation.lat}, ${lastJobLocation.lng})` : 'default location'}`);
  }
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