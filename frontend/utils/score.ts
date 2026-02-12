import type { ScoreRange } from '~/types'

/**
 * Determines score range category
 */
export function getScoreRange(score: number): ScoreRange {
  if (score >= 0.8) return 'excellent'
  if (score >= 0.6) return 'good'
  if (score >= 0.4) return 'fair'
  return 'low'
}
