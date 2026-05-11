import { describe, it, expect } from 'vitest'

// ── kpiColor ──────────────────────────────────────────────────────────
// Mirrors BriefingCard.vue: delta_direction drives color; index cycles
// through KPI_COLORS as a fallback when direction is absent/flat.

type BriefingKpi = { label: string; value: string; delta_vs_prev?: string | null; delta_direction?: 'up' | 'down' | 'flat' | null }

const KPI_COLORS = ['#22c55e', '#ef4444', '#7c3aed']

function kpiColor(kpi: BriefingKpi, index: number): string {
  if (kpi.delta_direction === 'up') return '#22c55e'
  if (kpi.delta_direction === 'down') return '#ef4444'
  return KPI_COLORS[index % KPI_COLORS.length]
}

// ── stripLeadingNumber ────────────────────────────────────────────────
// Mirrors the function used in BriefingCard.vue and ChatBriefingView.vue.
// Must strip LLM-generated number prefixes so the component's own
// counter (e.g. "1.") doesn't produce "1. 1) Heading".

function stripLeadingNumber(heading: string) {
  return heading.replace(/^\d+[\.\)\:\s]\s*/, '').trim()
}

// ── formatShort ───────────────────────────────────────────────────────
// Mirrors the timestamp formatter used in InfoPanelBriefings.vue.

function formatShort(s: string, nowMs: number = Date.now()) {
  const diffMs = nowMs - new Date(s).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(diffMs / 3600000)
  if (hours < 24) return `${hours}h`
  if (hours < 48) return 'yesterday'
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// ── formatRelative ────────────────────────────────────────────────────
// Mirrors the hero-card timestamp in InfoPanelBriefings.vue.

function formatRelative(s: string, nowMs: number = Date.now()) {
  const diffMs = nowMs - new Date(s).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  if (hours < 48) return 'yesterday'
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// ─────────────────────────────────────────────────────────────────────

describe('kpiColor', () => {
  const base = { label: 'Revenue', value: '$1M' }

  it('returns green for delta_direction "up"', () => {
    expect(kpiColor({ ...base, delta_direction: 'up' }, 0)).toBe('#22c55e')
  })
  it('returns red for delta_direction "down"', () => {
    expect(kpiColor({ ...base, delta_direction: 'down' }, 0)).toBe('#ef4444')
  })
  it('"up" overrides index-based color even at index 1', () => {
    expect(kpiColor({ ...base, delta_direction: 'up' }, 1)).toBe('#22c55e')
  })
  it('"down" overrides index-based color even at index 2', () => {
    expect(kpiColor({ ...base, delta_direction: 'down' }, 2)).toBe('#ef4444')
  })
  it('cycles through KPI_COLORS by index when direction is "flat"', () => {
    expect(kpiColor({ ...base, delta_direction: 'flat' }, 0)).toBe(KPI_COLORS[0])
    expect(kpiColor({ ...base, delta_direction: 'flat' }, 1)).toBe(KPI_COLORS[1])
    expect(kpiColor({ ...base, delta_direction: 'flat' }, 2)).toBe(KPI_COLORS[2])
  })
  it('cycles through KPI_COLORS by index when direction is null', () => {
    expect(kpiColor({ ...base, delta_direction: null }, 0)).toBe(KPI_COLORS[0])
    expect(kpiColor({ ...base, delta_direction: null }, 3)).toBe(KPI_COLORS[0])
    expect(kpiColor({ ...base, delta_direction: null }, 4)).toBe(KPI_COLORS[1])
  })
  it('cycles through KPI_COLORS by index when direction is absent', () => {
    expect(kpiColor({ ...base }, 0)).toBe(KPI_COLORS[0])
    expect(kpiColor({ ...base }, 1)).toBe(KPI_COLORS[1])
    expect(kpiColor({ ...base }, 2)).toBe(KPI_COLORS[2])
    expect(kpiColor({ ...base }, 3)).toBe(KPI_COLORS[0]) // wraps
  })
})

describe('stripLeadingNumber', () => {
  it('strips "1." prefix', () => {
    expect(stripLeadingNumber('1. Price trend')).toBe('Price trend')
  })
  it('strips "1)" prefix', () => {
    expect(stripLeadingNumber('1) Price trend')).toBe('Price trend')
  })
  it('strips "2:" prefix', () => {
    expect(stripLeadingNumber('2: Mix shift')).toBe('Mix shift')
  })
  it('strips "3 " prefix (space-separated number)', () => {
    expect(stripLeadingNumber('3 Room type matters')).toBe('Room type matters')
  })
  it('does not strip non-numeric prefixes', () => {
    expect(stripLeadingNumber('Price trend rising')).toBe('Price trend rising')
  })
  it('does not strip mid-sentence numbers', () => {
    expect(stripLeadingNumber('Revenue up 12% YoY')).toBe('Revenue up 12% YoY')
  })
  it('handles extra whitespace after prefix', () => {
    expect(stripLeadingNumber('1.   Extra spaces')).toBe('Extra spaces')
  })
  it('handles two-digit section number', () => {
    expect(stripLeadingNumber('10. Long report heading')).toBe('Long report heading')
  })
  it('returns empty string unchanged', () => {
    expect(stripLeadingNumber('')).toBe('')
  })
})

describe('formatShort', () => {
  const NOW = new Date('2026-05-11T10:00:00Z').getTime()

  it('returns "Xm" for < 60 minutes ago', () => {
    const ts = new Date(NOW - 5 * 60 * 1000).toISOString()
    expect(formatShort(ts, NOW)).toBe('5m')
  })
  it('returns "0m" for very recent', () => {
    const ts = new Date(NOW - 30 * 1000).toISOString()
    expect(formatShort(ts, NOW)).toBe('0m')
  })
  it('returns "Xh" for < 24 hours ago', () => {
    const ts = new Date(NOW - 3 * 3600 * 1000).toISOString()
    expect(formatShort(ts, NOW)).toBe('3h')
  })
  it('returns "yesterday" for 24–48 hours ago', () => {
    const ts = new Date(NOW - 30 * 3600 * 1000).toISOString()
    expect(formatShort(ts, NOW)).toBe('yesterday')
  })
  it('returns short date for older items', () => {
    const ts = new Date(NOW - 5 * 24 * 3600 * 1000).toISOString()
    const result = formatShort(ts, NOW)
    expect(result).toMatch(/\w+ \d+/) // e.g. "May 6"
  })
})

describe('formatRelative', () => {
  const NOW = new Date('2026-05-11T10:00:00Z').getTime()

  it('returns "just now" for < 1 minute ago', () => {
    const ts = new Date(NOW - 30 * 1000).toISOString()
    expect(formatRelative(ts, NOW)).toBe('just now')
  })
  it('returns "Xm ago" for < 60 minutes ago', () => {
    const ts = new Date(NOW - 8 * 60 * 1000).toISOString()
    expect(formatRelative(ts, NOW)).toBe('8m ago')
  })
  it('returns "Xh ago" for < 24 hours ago', () => {
    const ts = new Date(NOW - 2 * 3600 * 1000).toISOString()
    expect(formatRelative(ts, NOW)).toBe('2h ago')
  })
  it('returns "yesterday" for 24–48 hours ago', () => {
    const ts = new Date(NOW - 36 * 3600 * 1000).toISOString()
    expect(formatRelative(ts, NOW)).toBe('yesterday')
  })
  it('returns short date for older items', () => {
    const ts = new Date(NOW - 7 * 24 * 3600 * 1000).toISOString()
    const result = formatRelative(ts, NOW)
    expect(result).toMatch(/\w+ \d+/)
  })
})
