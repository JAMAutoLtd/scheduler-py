import { createClient, SupabaseClient } from '@supabase/supabase-js';

// Load environment variables (consider using a library like dotenv)
// Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set in your environment
const supabaseUrl = process.env.SUPABASE_URL;
const supabaseAnonKey = process.env.SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Supabase URL and Anon Key must be provided in environment variables.');
}

// Create a single supabase client for interacting with your database
export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseAnonKey); 