import { describe, it, expect } from 'vitest'
import type { DatabaseConnection, ConnectorType } from '~/types/connection'

/**
 * Pure logic tests for connection card metadata rendering.
 * Tests the helper functions extracted from SettingsConnections.vue.
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
    is_ephemeral: false,
    schema_fingerprint: null,
    ...overrides,
  }
}

function makeConnectorType(overrides: Partial<ConnectorType> & { id: string }): ConnectorType {
  return {
    display_name: 'Test',
    description: 'Test connector',
    default_port: 0,
    badge_variant: 'info',
    version: '1.0.0',
    card_meta_items: [],
    ...overrides,
  }
}

// Extracted helper logic (mirrors SettingsConnections.vue)
function getAccentClass(connection: DatabaseConnection): string {
  if (connection.profiling_status === 'in_progress' || connection.profiling_status === 'pending') {
    return 'bg-yellow-400'
  }
  return connection.is_active ? 'bg-green-500' : 'bg-red-500'
}

function getProfilingLabel(connection: DatabaseConnection): string {
  switch (connection.profiling_status) {
    case 'ready': return 'Profiled'
    case 'in_progress': return 'Profiling...'
    case 'pending': return 'Queued'
    case 'failed': return 'Failed'
    default: return 'Pending'
  }
}

function getProfilingIconClass(connection: DatabaseConnection): string {
  switch (connection.profiling_status) {
    case 'ready': return 'text-green-600'
    case 'in_progress': return 'text-yellow-500'
    case 'pending': return 'text-gray-400'
    case 'failed': return 'text-red-500'
    default: return 'text-gray-400'
  }
}

function parseLookbackDays(connection: DatabaseConnection): string {
  if (connection.source_filename) {
    try {
      const meta = JSON.parse(connection.source_filename)
      if (meta.lookback_days) return String(meta.lookback_days)
    } catch {}
  }
  return '7'
}

/**
 * Compute which meta items should render for a connection based on its connector type.
 * Profiling status is always first (handled separately in the template), then
 * items from card_meta_items are shown if the relevant data exists.
 */
function getVisibleMetaItems(connection: DatabaseConnection, connectorType: ConnectorType): string[] {
  const visible: string[] = []
  for (const item of connectorType.card_meta_items) {
    if (item === 'ssl' && connection.ssl_enabled) visible.push('ssl')
    else if (item === 'table_count' && connection.table_count != null) visible.push('table_count')
    else if (item === 'schema_date' && connection.schema_generated_at) visible.push('schema_date')
    else if (item === 'lookback') visible.push('lookback')
    else if (item === 'last_sync' && connection.schema_generated_at) visible.push('last_sync')
  }
  return visible
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

  it('returns green for active with failed profiling (connection still active)', () => {
    const conn = makeConnection({ id: 1, name: 'Test', is_active: true, profiling_status: 'failed' })
    expect(getAccentClass(conn)).toBe('bg-green-500')
  })
})

describe('getProfilingLabel', () => {
  it('returns Profiled for ready status', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'ready' })
    expect(getProfilingLabel(conn)).toBe('Profiled')
  })

  it('returns Profiling... for in_progress status', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'in_progress' })
    expect(getProfilingLabel(conn)).toBe('Profiling...')
  })

  it('returns Queued for pending status', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'pending' })
    expect(getProfilingLabel(conn)).toBe('Queued')
  })

  it('returns Failed for failed status', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'failed' })
    expect(getProfilingLabel(conn)).toBe('Failed')
  })
})

describe('getProfilingIconClass', () => {
  it('returns green for ready', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'ready' })
    expect(getProfilingIconClass(conn)).toBe('text-green-600')
  })

  it('returns yellow for in_progress', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'in_progress' })
    expect(getProfilingIconClass(conn)).toBe('text-yellow-500')
  })

  it('returns red for failed', () => {
    const conn = makeConnection({ id: 1, name: 'Test', profiling_status: 'failed' })
    expect(getProfilingIconClass(conn)).toBe('text-red-500')
  })
})

describe('parseLookbackDays', () => {
  it('parses lookback_days from JSON source_filename', () => {
    const conn = makeConnection({
      id: 1,
      name: 'Test',
      source_filename: '{"token_refreshed_at": "2026-01-01", "lookback_days": 30}',
    })
    expect(parseLookbackDays(conn)).toBe('30')
  })

  it('returns default 7 for non-JSON source_filename', () => {
    const conn = makeConnection({ id: 1, name: 'Test', source_filename: 'report.csv' })
    expect(parseLookbackDays(conn)).toBe('7')
  })

  it('returns default 7 when source_filename is null', () => {
    const conn = makeConnection({ id: 1, name: 'Test', source_filename: null })
    expect(parseLookbackDays(conn)).toBe('7')
  })
})

describe('getVisibleMetaItems', () => {
  it('shows ssl, table_count, schema_date for postgres with all data', () => {
    const conn = makeConnection({
      id: 1,
      name: 'Test',
      ssl_enabled: true,
      table_count: 24,
      schema_generated_at: '2026-01-01',
    })
    const type = makeConnectorType({ id: 'postgres', card_meta_items: ['ssl', 'table_count', 'schema_date'] })
    expect(getVisibleMetaItems(conn, type)).toEqual(['ssl', 'table_count', 'schema_date'])
  })

  it('hides ssl when not enabled', () => {
    const conn = makeConnection({
      id: 1,
      name: 'Test',
      ssl_enabled: false,
      table_count: 24,
      schema_generated_at: '2026-01-01',
    })
    const type = makeConnectorType({ id: 'postgres', card_meta_items: ['ssl', 'table_count', 'schema_date'] })
    expect(getVisibleMetaItems(conn, type)).toEqual(['table_count', 'schema_date'])
  })

  it('shows only schema_date for dataset connector', () => {
    const conn = makeConnection({
      id: 1,
      name: 'Test',
      db_type: 'dataset',
      schema_generated_at: '2026-01-01',
      source_filename: 'data.csv',
    })
    const type = makeConnectorType({ id: 'dataset', card_meta_items: ['schema_date'] })
    expect(getVisibleMetaItems(conn, type)).toEqual(['schema_date'])
  })

  it('shows lookback and last_sync for facebook_ads', () => {
    const conn = makeConnection({
      id: 1,
      name: 'Test',
      db_type: 'facebook_ads',
      schema_generated_at: '2026-01-01',
      source_filename: '{"lookback_days": 30}',
    })
    const type = makeConnectorType({ id: 'facebook_ads', card_meta_items: ['lookback', 'last_sync'] })
    expect(getVisibleMetaItems(conn, type)).toEqual(['lookback', 'last_sync'])
  })

  it('hides last_sync when schema_generated_at is null', () => {
    const conn = makeConnection({
      id: 1,
      name: 'Test',
      db_type: 'facebook_ads',
      schema_generated_at: null,
    })
    const type = makeConnectorType({ id: 'facebook_ads', card_meta_items: ['lookback', 'last_sync'] })
    expect(getVisibleMetaItems(conn, type)).toEqual(['lookback'])
  })

  it('returns empty array for connector with no meta items', () => {
    const conn = makeConnection({ id: 1, name: 'Test' })
    const type = makeConnectorType({ id: 'test', card_meta_items: [] })
    expect(getVisibleMetaItems(conn, type)).toEqual([])
  })

  it('sqlite shows table_count and schema_date but not ssl', () => {
    const conn = makeConnection({
      id: 1,
      name: 'Test',
      db_type: 'sqlite',
      table_count: 8,
      schema_generated_at: '2026-01-01',
      ssl_enabled: false,
    })
    const type = makeConnectorType({ id: 'sqlite', card_meta_items: ['table_count', 'schema_date'] })
    expect(getVisibleMetaItems(conn, type)).toEqual(['table_count', 'schema_date'])
  })
})
