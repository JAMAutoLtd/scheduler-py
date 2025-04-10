import { supabase } from './client';
import { Technician, Van, User, Address } from '../types/database.types';

/**
 * Fetches active technicians along with their assigned van details and home location coordinates.
 * Uses inner joins, so only technicians with a valid linked user and home address are returned.
 * TODO: Determine the criteria for 'active' technicians if needed (e.g., based on a status field).
 *
 * @returns {Promise<Technician[]>} A promise that resolves to an array of technicians with home locations.
 */
export async function getActiveTechnicians(): Promise<Technician[]> {
  console.log('Fetching active technicians with home locations...');

  const { data, error } = await supabase
    .from('technicians')
    .select(`
      id,
      user_id,
      assigned_van_id,
      workload,
      users!inner (
        id,
        full_name,
        phone,
        home_address_id,
        is_admin,
        customer_type,
        addresses!inner (
          lat,
          lng
        )
      ),
      vans ( id, vin, lat, lng, last_service, next_service )
    `)
    ;

  if (error) {
    console.error('Error fetching technicians with home locations:', error);
    throw new Error(`Failed to fetch technicians: ${error.message} (Details: ${error.details})`);
  }

  if (!data) {
    console.warn('No technicians found (or none with valid user/home address).');
    return [];
  }

  console.log(`Fetched ${data.length} raw technician entries.`);

  // Map and filter the raw data to the Technician interface
  const technicians: Technician[] = data
    .map((techRaw: any): Technician | null => { // Return type includes null
      // Validate the structure returned by Supabase
      const userJoin = techRaw.users;
      if (!userJoin || typeof userJoin !== 'object' || Array.isArray(userJoin)) {
        console.warn(`Technician ${techRaw.id} has invalid user join data. Skipping.`);
        return null;
      }

      const addressJoin = userJoin.addresses;
      if (!addressJoin || typeof addressJoin !== 'object' || Array.isArray(addressJoin)) {
        console.warn(`Technician ${techRaw.id} (User ${userJoin.id}) has invalid address join data. Skipping.`);
        return null;
      }
      
      // Cast to expected types after validation
      const user = userJoin as User; 
      const homeAddress = addressJoin as Address;
      const van = Array.isArray(techRaw.vans) && techRaw.vans.length > 0 ? techRaw.vans[0] as Van : undefined;

      // Create home_location object
      let homeLocation: { lat: number; lng: number } | undefined = undefined;
      if (homeAddress?.lat != null && homeAddress?.lng != null) {
        homeLocation = { lat: homeAddress.lat, lng: homeAddress.lng };
      } else {
        console.warn(`Technician ${techRaw.id} (User ${user.id}) has missing home address coordinates.`);
      }

      // Construct the final Technician object strictly matching the interface
      const technicianData: Technician = {
        id: techRaw.id,
        user_id: techRaw.user_id,
        assigned_van_id: techRaw.assigned_van_id,
        workload: techRaw.workload,
        user: user, // Assign the validated User object
        van: van, // van can be undefined, matching Technician interface
        home_location: homeLocation, // home_location is optional
        current_location: (van?.lat != null && van?.lng != null) ? { lat: van.lat, lng: van.lng } : undefined,
        earliest_availability: undefined, // earliest_availability is optional
      };
      return technicianData;
    })
    // Filter out entries that failed validation (returned null)
    .filter((t): t is Technician => t !== null);

  console.log(`Returning ${technicians.length} technicians mapped successfully.`);
  return technicians;
}

// Example usage
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