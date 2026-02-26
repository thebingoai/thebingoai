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

export type SkillType = 'code' | 'prompt' | 'instruction' | 'hybrid'

export interface SkillReference {
  id: string
  title: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface UserSkill {
  id: string
  name: string
  description: string
  skill_type: SkillType
  has_prompt_template: boolean
  has_code: boolean
  has_instructions: boolean
  reference_count: number
  version: number
  parameters_schema: Record<string, any> | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserSkillDetail extends UserSkill {
  instructions: string | null
  prompt_template: string | null
  activation_hint: string | null
  references: SkillReference[]
}

export interface SkillSuggestion {
  id: string
  suggested_name: string
  suggested_description: string | null
  suggested_skill_type: SkillType
  pattern_summary: string | null
  confidence: number
  status: string
  created_at: string
}
