export interface SkillSuggestion {
  id: string
  suggested_name: string
  suggested_description: string | null
  suggested_skill_type: string
  pattern_summary: string | null
  confidence: number
  status: string
  recommendation: string | null
  recommendation_reason: string | null
  frequency_count: number | null
  created_at: string
}
