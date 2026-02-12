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

/**
 * Gets Tailwind color class for a score
 */
export function getScoreColor(score: number): string {
  const range = getScoreRange(score)
  const colors: Record<ScoreRange, string> = {
    excellent: 'text-success-600 dark:text-success-500',
    good: 'text-info-600 dark:text-info-500',
    fair: 'text-warning-600 dark:text-warning-500',
    low: 'text-neutral-500 dark:text-neutral-400'
  }
  return colors[range]
}

/**
 * Gets background color class for score badges
 */
export function getScoreBadgeColor(score: number): string {
  const range = getScoreRange(score)
  const colors: Record<ScoreRange, string> = {
    excellent: 'bg-success-100 text-success-700 dark:bg-success-900/20 dark:text-success-400',
    good: 'bg-info-100 text-info-700 dark:bg-info-900/20 dark:text-info-400',
    fair: 'bg-warning-100 text-warning-700 dark:bg-warning-900/20 dark:text-warning-400',
    low: 'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400'
  }
  return colors[range]
}

/**
 * Gets label for score range
 */
export function getScoreLabel(score: number): string {
  const range = getScoreRange(score)
  const labels: Record<ScoreRange, string> = {
    excellent: 'Excellent',
    good: 'Good',
    fair: 'Fair',
    low: 'Low'
  }
  return labels[range]
}
