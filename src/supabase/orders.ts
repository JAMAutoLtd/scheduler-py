import { supabase } from './client';
import { YmmRef } from '../types/database.types';

/**
 * Fetches the ymm_id for a given order by looking up the order's vehicle
 * and matching its year, make, and model in the ymm_ref table.
 *
 * @param {number} orderId - The ID of the order.
 * @returns {Promise<number | null>} A promise that resolves to the ymm_id or null if not found.
 */
export async function getYmmIdForOrder(orderId: number): Promise<number | null> {
  console.log(`Fetching ymm_id for order ${orderId}...`);

  // 1. Fetch the order and its associated vehicle details
  const { data: orderData, error: orderError } = await supabase
    .from('orders')
    .select(`
      id,
      vehicle_id,
      customer_vehicles ( id, year, make, model )
    `)
    .eq('id', orderId)
    .single(); // Expecting only one order

  if (orderError) {
    // Handle case where order might not be found (e.g., error code PGROST 0 - no rows returned)
    if (orderError.code === 'PGRST0' || orderError.message.includes('JSON object requested, multiple (or no) rows returned')) {
      console.warn(`Order with ID ${orderId} not found.`);
      return null;
    } 
    console.error(`Error fetching order ${orderId}:`, orderError);
    throw new Error(`Failed to fetch order ${orderId}: ${orderError.message}`);
  }

  if (!orderData || !orderData.customer_vehicles) {
    console.warn(`Order ${orderId} found, but has no associated vehicle information.`);
    return null;
  }

  // Supabase join might return an array, handle it
  const vehicle = Array.isArray(orderData.customer_vehicles) 
    ? orderData.customer_vehicles[0] 
    : orderData.customer_vehicles;

  if (!vehicle || !vehicle.year || !vehicle.make || !vehicle.model) {
      console.warn(`Vehicle details (year, make, model) missing for order ${orderId}. Cannot determine ymm_id.`);
      return null;
  }

  // 2. Find the matching ymm_id in ymm_ref based on vehicle details
  const { data: ymmData, error: ymmError } = await supabase
    .from('ymm_ref')
    .select('ymm_id')
    .eq('year', vehicle.year)
    .eq('make', vehicle.make)
    .eq('model', vehicle.model)
    .single(); // Expecting a unique YMM combination

  if (ymmError) {
    if (ymmError.code === 'PGRST0' || ymmError.message.includes('JSON object requested, multiple (or no) rows returned')) {
        console.warn(`No ymm_ref entry found for vehicle: ${vehicle.year} ${vehicle.make} ${vehicle.model} (Order ID: ${orderId}).`);
        return null;
    }
    console.error(`Error fetching ymm_ref for vehicle ${vehicle.year} ${vehicle.make} ${vehicle.model}:`, ymmError);
    throw new Error(`Failed to fetch ymm_ref: ${ymmError.message}`);
  }

  if (!ymmData) {
    console.warn(`ymm_ref entry not found for vehicle on order ${orderId}.`);
    return null;
  }

  console.log(`Found ymm_id ${ymmData.ymm_id} for order ${orderId}.`);
  return ymmData.ymm_id;
}

// Example usage (can be removed later)
/*
async function runYmmExample() {
  try {
    const exampleOrderId = 1; // Replace with an actual order ID from your DB
    const ymmId = await getYmmIdForOrder(exampleOrderId);
    if (ymmId !== null) {
      console.log(`Successfully fetched ymm_id for order ${exampleOrderId}: ${ymmId}`);
    } else {
      console.log(`Could not find ymm_id for order ${exampleOrderId}.`);
    }
  } catch (err) {
    console.error('Failed to run ymm_id example:', err);
  }
}
runYmmExample();
*/ 