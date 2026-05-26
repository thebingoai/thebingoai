import { describe, it, expect } from 'vitest'
import type { DatabaseConnection } from '~/types/connection'

/**
 * Pure logic tests for ConnectionCardMeta's 4-slot strip.
 * Mirrors the resolvers in components/settings/ConnectionCardMeta.vue.
 */

function makeConnection(overrides: Partial<DatabaseConnection> & { id: number; name: string }): DatabaseConnection {
  return {
    db_type: 'postgres',
    host: 'localhost',
    port: 5432,
    database: 'testdb',
    username: 'user',
    ssl_enabled: false,
    has_ssl_ca_cert: false,
    user_id: 'user-1',
    is_active: true,
    schema_generated_at: null,
    table_count: null,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    source_filename: null,
    dataset_table_name: null,
    profiling_status: 'ready',
    profiling_progress: null,
    profiling_error: null,
    profiling_started_at: null,
    profiling_completed_at: null,
    is_ephemeral: false,
    schema_fingerprint: null,
    ...overrides,
  }
}

// Extracted helper logic (mirrors ConnectionCardMeta.vue)
function getAccentClass(connection: DatabaseConnection): string {
  if (connection.profiling_status === 'in_progress' || connection.profiling_status === 'pending') {
    return 'bg-yellow-400'
  }
  return connection.is_active ? 'bg-green-500' : 'bg-red-500'
}

type StatusSlot = { label: 'Healthy' | 'Error' | 'Profiling' | 'Unknown'; color: string; spin?: boolean }

function statusSlot(c: DatabaseConnection): StatusSlot {
  switch (c.profiling_status) {
    case 'ready':       return { label: 'Healthy',   color: 'text-green-600' }
    case 'failed':      return { label: 'Error',     color: 'text-red-500' }
    case 'in_progress':
    case 'pending':     return { label: 'Profiling', color: 'text-purple-600', spin: true }
    default:            return { label: 'Unknown',   color: 'text-gray-400' }
  }
}

function timeLabel(c: DatabaseConnection): string {
  if (c.profiling_status === 'in_progress' || c.profiling_status === 'pending') return 'Profiling'
  if (c.profiling_started_at) return 'relative'
  return '—'
}

function showTableCount(c: DatabaseConnection): boolean {
  return c.profiling_status === 'ready' && c.table_count != null
}

function showSsl(c: DatabaseConnection): boolean {
  return c.ssl_enabled === true
}

describe('getAccentClass', () => {
  it('returns green for active profiled connection', () => {
    const conn = makeConnection({ id: 1, name: 'Test', is_active: true, profiling_status: 'ready' })
    expect(getAccentClass(conn)).toBe('bg-green-500')
  })

  it('returns red for inactive connection', () => {
    const conn = makeConnection({ id: 1, name: 'Test', is_active: false, profiling_status: 'ready' })
    expect(getAccentClass(conn)).toBe('bg-red-500')
  })

  it('returns yellow for profiling in progress', () => {
    const conn = makeConnection({ id: 1, name: 'Test', is_active: true, profiling_status: 'in_progress' })
    expect(getAccentClass(conn)).toBe('bg-yellow-400')
  })

  it('returns yellow for pending profiling', () => {
    const conn = makeConnection({ id: 1, name: 'Test', is_active: true, profiling_status: 'pending' })
    expect(getAccentClass(conn)).toBe('bg-yellow-400')
  })
})

describe('statusSlot', () => {
  it('Healthy + green for ready', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'ready' })
    expect(statusSlot(conn)).toEqual({ label: 'Healthy', color: 'text-green-600' })
  })

  it('Error + red for failed', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'failed' })
    expect(statusSlot(conn)).toEqual({ label: 'Error', color: 'text-red-500' })
  })

  it('Profiling + purple + spin for in_progress', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'in_progress' })
    expect(statusSlot(conn)).toEqual({ label: 'Profiling', color: 'text-purple-600', spin: true })
  })

  it('Profiling + purple + spin for pending', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'pending' })
    expect(statusSlot(conn)).toEqual({ label: 'Profiling', color: 'text-purple-600', spin: true })
  })
})

describe('timeLabel', () => {
  it('returns "Profiling" while in_progress regardless of started_at', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'in_progress', profiling_started_at: '2026-01-01' })
    expect(timeLabel(conn)).toBe('Profiling')
  })

  it('returns "Profiling" while pending', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'pending' })
    expect(timeLabel(conn)).toBe('Profiling')
  })

  it('returns relative time when ready with started_at', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'ready', profiling_started_at: '2026-01-01' })
    expect(timeLabel(conn)).toBe('relative')
  })

  it('returns em-dash when ready but no started_at', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'ready', profiling_started_at: null })
    expect(timeLabel(conn)).toBe('—')
  })

  it('returns relative time when failed with started_at', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'failed', profiling_started_at: '2026-01-01' })
    expect(timeLabel(conn)).toBe('relative')
  })
})

describe('showTableCount', () => {
  it('shown only when ready AND table_count != null', () => {
    expect(showTableCount(makeConnection({ id: 1, name: 'T', profiling_status: 'ready', table_count: 24 }))).toBe(true)
  })

  it('hidden when ready but table_count is null', () => {
    expect(showTableCount(makeConnection({ id: 1, name: 'T', profiling_status: 'ready', table_count: null }))).toBe(false)
  })

  it('hidden while in_progress even with table_count', () => {
    expect(showTableCount(makeConnection({ id: 1, name: 'T', profiling_status: 'in_progress', table_count: 24 }))).toBe(false)
  })

  it('hidden on failed', () => {
    expect(showTableCount(makeConnection({ id: 1, name: 'T', profiling_status: 'failed', table_count: 24 }))).toBe(false)
  })
})

describe('showSsl', () => {
  it('shown when ssl_enabled', () => {
    expect(showSsl(makeConnection({ id: 1, name: 'T', ssl_enabled: true }))).toBe(true)
  })

  it('hidden when ssl_enabled is false', () => {
    expect(showSsl(makeConnection({ id: 1, name: 'T', ssl_enabled: false }))).toBe(false)
  })
})
