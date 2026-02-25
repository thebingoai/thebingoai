export interface Organization {
  id: string
  name: string
  created_at: string
}

export interface Team {
  id: string
  org_id: string
  name: string
  created_at: string
}

export interface TeamMember {
  id: string
  user_id: string
  user_email: string
  team_id: string
  role: string
  created_at: string
}

export interface ToolCatalogItem {
  id: string
  tool_key: string
  display_name: string
  description: string | null
  category: string
  is_system: boolean
}

export interface TeamToolPolicy {
  team_id: string
  tool_keys: string[]
}

export interface TeamConnectionPolicy {
  team_id: string
  connection_ids: number[]
}
