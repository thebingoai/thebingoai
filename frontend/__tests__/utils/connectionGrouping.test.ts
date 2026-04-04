import { describe, it, expect } from 'vitest'
import type { DatabaseConnection } from '~/types/connection'

/**
 * Pure logic extracted from SettingsConnections.vue computed properties.
 * Tests the grouping algorithm without Vue reactivity.
 */

interface DatasetGroup {
  fingerprint: string
  name: string
  connections: DatabaseConnection[]
}

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

function computeGroups(connections: DatabaseConnection[]): { groups: DatasetGroup[]; ungrouped: DatabaseConnection[] } {
  const fingerMap = new Map<string, DatabaseConnection[]>()
  for (const conn of connections) {
    if (conn.db_type === 'dataset' && conn.schema_fingerprint) {
      const existing = fingerMap.get(conn.schema_fingerprint) || []
      existing.push(conn)
      fingerMap.set(conn.schema_fingerprint, existing)
    }
  }

  const groups: DatasetGroup[] = []
  const groupedIds = new Set<number>()

  for (const [fingerprint, conns] of fingerMap) {
    if (conns.length >= 2) {
      groups.push({ fingerprint, name: conns[0].name, connections: conns })
      for (const c of conns) groupedIds.add(c.id)
    }
  }

  const ungrouped = connections.filter(c => !groupedIds.has(c.id))
  return { groups, ungrouped }
}

describe('connectionGrouping', () => {
  it('groups 3 datasets with the same schema_fingerprint into one group', () => {
    const connections = [
      makeConnection({ id: 1, name: 'Sales Q1', db_type: 'dataset', schema_fingerprint: 'abc123' }),
      makeConnection({ id: 2, name: 'Sales Q2', db_type: 'dataset', schema_fingerprint: 'abc123' }),
      makeConnection({ id: 3, name: 'Sales Q3', db_type: 'dataset', schema_fingerprint: 'abc123' }),
    ]

    const { groups, ungrouped } = computeGroups(connections)
    expect(groups).toHaveLength(1)
    expect(groups[0].connections).toHaveLength(3)
    expect(groups[0].fingerprint).toBe('abc123')
    expect(ungrouped).toHaveLength(0)
  })

  it('displays single datasets (unique fingerprint) ungrouped', () => {
    const connections = [
      makeConnection({ id: 1, name: 'Dataset A', db_type: 'dataset', schema_fingerprint: 'unique1' }),
      makeConnection({ id: 2, name: 'Dataset B', db_type: 'dataset', schema_fingerprint: 'unique2' }),
    ]

    const { groups, ungrouped } = computeGroups(connections)
    expect(groups).toHaveLength(0)
    expect(ungrouped).toHaveLength(2)
  })

  it('never groups non-dataset connections', () => {
    const connections = [
      makeConnection({ id: 1, name: 'Postgres 1', db_type: 'postgres', schema_fingerprint: 'same' }),
      makeConnection({ id: 2, name: 'Postgres 2', db_type: 'postgres', schema_fingerprint: 'same' }),
      makeConnection({ id: 3, name: 'MySQL', db_type: 'mysql', schema_fingerprint: null }),
    ]

    const { groups, ungrouped } = computeGroups(connections)
    expect(groups).toHaveLength(0)
    expect(ungrouped).toHaveLength(3)
  })

  it('deleting one dataset from a group removes only that dataset', () => {
    const connections = [
      makeConnection({ id: 1, name: 'Sales Q1', db_type: 'dataset', schema_fingerprint: 'abc123' }),
      makeConnection({ id: 2, name: 'Sales Q2', db_type: 'dataset', schema_fingerprint: 'abc123' }),
      makeConnection({ id: 3, name: 'Sales Q3', db_type: 'dataset', schema_fingerprint: 'abc123' }),
    ]

    // Simulate deleting connection id=2
    const afterDelete = connections.filter(c => c.id !== 2)
    const { groups, ungrouped } = computeGroups(afterDelete)

    // Still grouped (2 remaining)
    expect(groups).toHaveLength(1)
    expect(groups[0].connections).toHaveLength(2)
    expect(groups[0].connections.map(c => c.id)).toEqual([1, 3])
    expect(ungrouped).toHaveLength(0)
  })

  it('mixed: groups datasets with shared fingerprint, leaves others ungrouped', () => {
    const connections = [
      makeConnection({ id: 1, name: 'Postgres Prod', db_type: 'postgres' }),
      makeConnection({ id: 2, name: 'Sales Q1', db_type: 'dataset', schema_fingerprint: 'fp1' }),
      makeConnection({ id: 3, name: 'Sales Q2', db_type: 'dataset', schema_fingerprint: 'fp1' }),
      makeConnection({ id: 4, name: 'Unique Dataset', db_type: 'dataset', schema_fingerprint: 'fp2' }),
    ]

    const { groups, ungrouped } = computeGroups(connections)
    expect(groups).toHaveLength(1)
    expect(groups[0].connections).toHaveLength(2)
    expect(ungrouped).toHaveLength(2) // Postgres Prod + Unique Dataset
    expect(ungrouped.map(c => c.id)).toEqual([1, 4])
  })
})
