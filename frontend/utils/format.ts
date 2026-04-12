import { formatDistanceToNow, format as dateFnsFormat, isToday, isYesterday, isSameDay } from 'date-fns'

/**
 * Parses a date string as UTC, appending Z when no timezone designator is present.
 * The backend stores timezone-naive datetimes (UTC) and serializes them without Z,
 * so without this fix JavaScript treats them as local time instead of UTC.
 */
export function parseUtcDate(date: string | Date): Date {
  if (date instanceof Date) return date
  const s = date.trim()
  if (!s.endsWith('Z') && !/[+-]\d{2}:\d{2}$/.test(s)) {
    return new Date(s + 'Z')
  }
  return new Date(s)
}

/**
 * Formats a date to a relative time string (e.g., "2 hours ago")
 */
export function timeAgo(date: string | Date): string {
  return formatDistanceToNow(parseUtcDate(date), { addSuffix: true })
}

/**
 * Formats a date to a specific format
 */
export function formatDate(date: string | Date, formatStr: string = 'MMM d, yyyy HH:mm'): string {
  return dateFnsFormat(parseUtcDate(date), formatStr)
}

/**
 * Returns a human-readable date label: "Today", "Yesterday", or "Month D, YYYY"
 */
export function formatDateLabel(date: string | Date): string {
  const d = parseUtcDate(date)
  if (isToday(d)) return 'Today'
  if (isYesterday(d)) return 'Yesterday'
  return dateFnsFormat(d, 'MMMM d, yyyy')
}

export { isSameDay }

/**
 * Truncates a string to a maximum length with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str
  return `${str.slice(0, maxLength)}...`
}
