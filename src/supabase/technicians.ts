import { supabase } from './client';
import { Technician, Van, User } from '../types/database.types';

/**
 * Fetches active technicians along with their assigned van details.
 * TODO: Determine the criteria for 'active' technicians (e.g., based on a status field or just existence in the table).
 * TODO: Implement fetching real-time van location (lat, lng) if available, otherwise default to home base or last known job.
 *
 * @returns {Promise<Technician[]>} A promise that resolves to an array of technicians.
 */
export async function getActiveTechnicians(): Promise<Technician[]> {
  console.log('Fetching active technicians...');

  // Select technicians and join their user and van details
  // Assumes van lat/lng are stored directly on the van record for now.
  const { data, error } = await supabase
    .from('technicians')
    .select(`
      id,
      user_id,
      assigned_van_id,
      workload,
      users ( id, full_name, phone, home_address_id ),
      vans ( id, vin, lat, lng, last_service, next_service )
    `)
    // .eq('is_active', true) // Example filter if an 'is_active' field exists
    ;

  if (error) {
    console.error('Error fetching technicians:', error);
    throw new Error(`Failed to fetch technicians: ${error.message}`);
  }

  if (!data) {
    console.warn('No technicians found.');
    return [];
  }

  console.log(`Fetched ${data.length} technicians.`);

  // Map the raw data to the Technician interface
  const technicians: Technician[] = data.map((tech) => {
    // Type assertion needed as Supabase joins return potentially partial or differently structured objects
    // Access the first element if the array is not empty, assuming a one-to-one relationship
    const user = Array.isArray(tech.users) && tech.users.length > 0 ? tech.users[0] as User : undefined;
    const van = Array.isArray(tech.vans) && tech.vans.length > 0 ? tech.vans[0] as Van : undefined;

    return {
      id: tech.id,
      user_id: tech.user_id,
      assigned_van_id: tech.assigned_van_id,
      workload: tech.workload,
      user: user,
      van: van,
      // Placeholder for current location - needs actual implementation
      // This might involve checking van table, or a separate technician location tracking table/system
      current_location: van?.lat && van?.lng ? { lat: van.lat, lng: van.lng } : undefined,
      // Placeholder for availability - will be calculated later based on current time and locked jobs
      earliest_availability: undefined,
    };
  });

  return technicians;
}

// Example usage (can be removed later)
/*
getActiveTechnicians()
  .then(technicians => {
    console.log('Successfully fetched technicians:');
    console.log(JSON.stringify(technicians, null, 2));
  })
  .catch(err => {
    console.error('Failed to run example:', err);
  });
*/ 