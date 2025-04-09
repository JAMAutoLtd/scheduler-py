import { runFullReplan } from './scheduler/orchestrator';
import { supabase } from './supabase/client';

/**
 * Main entry point for the scheduler application.
 */
async function main() {
  console.log('Starting scheduler process...');
  try {
    // Pass the Supabase client instance to the replan function
    await runFullReplan(supabase);
    console.log('Scheduler process finished successfully.');
    process.exit(0); // Exit cleanly
  } catch (error) {
    console.error('Scheduler process failed:', error);
    process.exit(1); // Exit with error code
  }
}

// Execute the main function
main(); 