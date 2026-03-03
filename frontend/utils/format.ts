import { formatDistanceToNow, format as dateFnsFormat, isToday, isYesterday, isSameDay } from 'date-fns'

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
 * Returns a human-readable date label: "Today", "Yesterday", or "Month D, YYYY"
 */
export function formatDateLabel(date: Date): string {
  if (isToday(date)) return 'Today'
  if (isYesterday(date)) return 'Yesterday'
  return dateFnsFormat(date, 'MMMM d, yyyy')
}

export { isSameDay }

/**
 * Truncates a string to a maximum length with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return `${str.slice(0, maxLength)}...`
}
