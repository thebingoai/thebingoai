import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { timeAgo, formatDate, formatDateLabel, truncate } from '~/utils/format'

describe('utils/format', () => {
  describe('timeAgo', () => {
    it('returns a string containing "ago"', () => {
      const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000)
      const result = timeAgo(oneHourAgo)
      expect(result).toContain('ago')
    })
  })

  describe('formatDate', () => {
    it('formats with default format (MMM d, yyyy HH:mm)', () => {
      const date = new Date(2024, 0, 15, 14, 30) // Jan 15, 2024 14:30
      const result = formatDate(date)
      expect(result).toBe('Jan 15, 2024 14:30')
    })

    it('formats with a custom format string', () => {
      const date = new Date(2024, 5, 3) // June 3, 2024
      const result = formatDate(date, 'yyyy-MM-dd')
      expect(result).toBe('2024-06-03')
    })
  })

  describe('formatDateLabel', () => {
    it('returns "Today" for today\'s date', () => {
      const today = new Date()
      expect(formatDateLabel(today)).toBe('Today')
    })

    it('returns "Yesterday" for yesterday\'s date', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      expect(formatDateLabel(yesterday)).toBe('Yesterday')
    })

    it('returns "Month D, YYYY" format for older dates', () => {
      const oldDate = new Date(2023, 2, 15) // March 15, 2023
      expect(formatDateLabel(oldDate)).toBe('March 15, 2023')
    })
  })

  describe('truncate', () => {
    it('returns the original string when within the limit', () => {
      expect(truncate('hello', 10)).toBe('hello')
    })

    it('truncates with "..." when over the limit', () => {
      expect(truncate('hello world', 5)).toBe('hello...')
    })
  })
})
