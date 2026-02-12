import { formatDistanceToNow, format as dateFnsFormat } from 'date-fns'

/**
 * Formats a date to a relative time string (e.g., "2 hours ago")
 */
export function timeAgo(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: true })
}

/**
 * Formats a date to a specific format
 */
export function formatDate(date: string | Date, formatStr: string = 'MMM d, yyyy HH:mm'): string {
  return dateFnsFormat(new Date(date), formatStr)
}

/**
 * Truncates a string to a maximum length with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return `${str.slice(0, maxLength)}...`
}
