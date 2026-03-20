import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let _client: SupabaseClient | null = null

export const useSupabase = (): SupabaseClient => {
  if (!_client) {
    const config = useRuntimeConfig()
    const url = config.public.supabaseUrl as string
    const anonKey = config.public.supabaseAnonKey as string

    if (!url || !anonKey) {
      throw new Error('Supabase URL and anon key must be configured in runtime config')
    }

    _client = createClient(url, anonKey)
  }

  return _client
}
