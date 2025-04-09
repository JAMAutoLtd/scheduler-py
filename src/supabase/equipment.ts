import { supabase } from './client';
import { VanEquipment, Equipment, Job, ServiceCategory, EquipmentRequirement } from '../types/database.types';
import { getYmmIdForOrder } from './orders'; // Import the helper function

// Mapping from service category to the corresponding equipment requirement table name
const requirementTableMap: Record<ServiceCategory, string> = {
  adas: 'adas_equipment_requirements',
  airbag: 'airbag_equipment_requirements',
  immo: 'immo_equipment_requirements',
  prog: 'prog_equipment_requirements',
  diag: 'diag_equipment_requirements',
};

/**
 * Fetches the equipment inventory for a given list of van IDs.
 *
 * @param {number[]} vanIds - An array of van IDs to fetch equipment for.
 * @returns {Promise<Map<number, VanEquipment[]>>} A promise that resolves to a map where keys are van IDs
 *                                                  and values are arrays of VanEquipment for that van.
 */
export async function getEquipmentForVans(vanIds: number[]): Promise<Map<number, VanEquipment[]>> {
  const equipmentMap = new Map<number, VanEquipment[]>();
  if (vanIds.length === 0) {
    console.warn('No van IDs provided to getEquipmentForVans.');
    return equipmentMap;
  }

  console.log(`Fetching equipment for ${vanIds.length} vans...`);

  const { data, error } = await supabase
    .from('van_equipment')
    .select(`
      van_id,
      equipment_id,
      equipment_model,
      equipment ( id, equipment_type, model ) 
    `)
    .in('van_id', vanIds);

  if (error) {
    console.error('Error fetching van equipment:', error);
    throw new Error(`Failed to fetch van equipment: ${error.message}`);
  }

  if (!data) {
    console.warn('No equipment found for the specified vans.');
    return equipmentMap;
  }

  // Group equipment by van_id
  for (const item of data) {
    // Handle joined equipment data (assuming one-to-one relationship)
    const equipment = Array.isArray(item.equipment) && item.equipment.length > 0
      ? item.equipment[0] as Equipment
      : undefined;

    const vanEquipment: VanEquipment = {
      van_id: item.van_id,
      equipment_id: item.equipment_id,
      equipment_model: item.equipment_model,
      equipment: equipment,
    };

    if (!equipmentMap.has(item.van_id)) {
      equipmentMap.set(item.van_id, []);
    }
    equipmentMap.get(item.van_id)?.push(vanEquipment);
  }

  console.log(`Fetched equipment details for ${equipmentMap.size} vans.`);
  return equipmentMap;
}

/**
 * Determines the required equipment model(s) for a specific job.
 *
 * @param {Job} job - The job object (must include service details).
 * @returns {Promise<string[]>} A promise that resolves to an array of required equipment model strings, or an empty array if none are found or required.
 */
export async function getRequiredEquipmentForJob(job: Job): Promise<string[]> {
  if (!job.service || !job.service.service_category) {
    console.warn(`Job ${job.id} is missing service category information. Cannot determine required equipment.`);
    return [];
  }
  if (!job.order_id) {
     console.warn(`Job ${job.id} is missing order_id. Cannot determine required equipment.`);
     return [];
  }

  console.log(`Determining required equipment for Job ID: ${job.id}, Service Category: ${job.service.service_category}`);

  // 1. Get the ymm_id for the order associated with the job
  const ymmId = await getYmmIdForOrder(job.order_id);
  if (ymmId === null) {
    console.warn(`Could not determine ymm_id for order ${job.order_id} (Job ID: ${job.id}). Cannot fetch equipment requirements.`);
    return [];
  }

  // 2. Determine the correct requirement table
  const tableName = requirementTableMap[job.service.service_category];
  if (!tableName) {
    // This case should ideally not happen if service_category enum is enforced
    console.error(`Invalid service category '${job.service.service_category}' for job ${job.id}. No requirement table mapped.`);
    return [];
  }

  console.log(`Querying table '${tableName}' for ymm_id: ${ymmId}, service_id: ${job.service_id}`);

  // 3. Query the specific requirements table
  const { data, error } = await supabase
    .from(tableName)
    .select('equipment_model') // Select only the equipment model string(s)
    .eq('ymm_id', ymmId)
    .eq('service_id', job.service_id);
    // Note: DB schema suggests unique constraint on (ymm_id, service_id), but let's handle potential multiple rows just in case

  if (error) {
    // Don't throw, just warn and return empty - maybe this specific combo doesn't require equipment
    console.warn(`Could not fetch equipment requirements from ${tableName} for ymm_id ${ymmId}, service_id ${job.service_id}: ${error.message}`);
    return [];
  }

  if (!data || data.length === 0) {
    console.log(`No specific equipment requirement found in ${tableName} for ymm_id ${ymmId}, service_id ${job.service_id}.`);
    return [];
  }

  // Extract the equipment model strings
  const requiredModels = data.map(req => req.equipment_model).filter(model => !!model); // Filter out any null/empty strings
  
  console.log(`Required equipment models for Job ID ${job.id}: ${requiredModels.join(', ')}`);
  return requiredModels;
}

// Example usage (can be removed later)
/*
async function runRequirementExample() {
  try {
    // Fetch a relevant job first (ensure it includes service details)
    const jobs = await getRelevantJobs(); // Assuming getRelevantJobs is defined elsewhere
    if (jobs.length > 0) {
        const testJob = jobs.find(j => j.service?.service_category); // Find a job with a service
        if(testJob){
            console.log(`Testing with Job ID: ${testJob.id}, Order ID: ${testJob.order_id}, Service ID: ${testJob.service_id}`);
            const requiredEquipment = await getRequiredEquipmentForJob(testJob);
            console.log(`Successfully determined required equipment for job ${testJob.id}:`, requiredEquipment);
        } else {
             console.log("Could not find a suitable job with service details for testing.");
        }
    } else {
      console.log("No relevant jobs found to test requirement fetching.");
    }
  } catch (err) {
    console.error('Failed to run requirement example:', err);
  }
}
// Assuming getRelevantJobs is available in this scope or imported
// import { getRelevantJobs } from './jobs'; 
// runRequirementExample(); 
*/ 