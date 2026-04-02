import { describe, it, expect, vi, beforeEach } from 'vitest'

// ── Mock sql.js ────────────────────────────────────────────────────

const mockExec = vi.fn()
const mockClose = vi.fn()

// Must be a real class so `new SQL.Database(...)` works
class MockDatabase {
  constructor(..._args: any[]) {
    // Vitest can't spy on constructors directly; track via mockExec/mockClose
  }
  exec(...args: any[]) { return mockExec(...args) }
  close(...args: any[]) { return mockClose(...args) }
}

vi.mock('sql.js', () => ({
  default: vi.fn(() =>
    Promise.resolve({
      Database: MockDatabase,
    })
  ),
}))

// ── Mock fetch (for downloading SQLite file) ───────────────────────

const mockArrayBuffer = vi.fn(() => Promise.resolve(new ArrayBuffer(8)))
vi.stubGlobal('fetch', vi.fn(() =>
  Promise.resolve({
    ok: true,
    statusText: 'OK',
    arrayBuffer: mockArrayBuffer,
  })
))

// ── Mock useApi as global (Nuxt auto-import) ───────────────────────

const mockGetSqliteUrl = vi.fn(() =>
  Promise.resolve({ url: 'https://example.com/db.sqlite', expires_in: 3600 })
)

vi.stubGlobal('useApi', () => ({
  dashboards: {
    getSqliteUrl: mockGetSqliteUrl,
  },
}))

// Need to reset module-level cache between tests
let useSqlite: typeof import('~/composables/useSqlite').useSqlite

describe('useSqlite', () => {
  beforeEach(async () => {
    vi.resetModules()
    mockExec.mockReset()
    mockClose.mockReset()
    mockGetSqliteUrl.mockClear()
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockClear()
    mockArrayBuffer.mockClear()

    // Re-stub useApi after resetModules
    vi.stubGlobal('useApi', () => ({
      dashboards: {
        getSqliteUrl: mockGetSqliteUrl,
      },
    }))

    const mod = await import('~/composables/useSqlite')
    useSqlite = mod.useSqlite
  })

  it('getDatabase fetches and creates a new database instance', async () => {
    const { getDatabase } = useSqlite()
    const db = await getDatabase(1)

    expect(mockGetSqliteUrl).toHaveBeenCalledWith(1)
    expect(globalThis.fetch).toHaveBeenCalledWith('https://example.com/db.sqlite')
    expect(db).toBeDefined()
    expect(db.exec).toBeDefined()
  })

  it('getDatabase returns cached instance on repeated calls', async () => {
    const { getDatabase } = useSqlite()

    const db1 = await getDatabase(1)
    const db2 = await getDatabase(1)

    expect(mockGetSqliteUrl).toHaveBeenCalledTimes(1)
    expect(db1).toBe(db2)
  })

  it('executeQuery returns columns and rows from db.exec', async () => {
    mockExec.mockReturnValue([
      { columns: ['id', 'name'], values: [[1, 'Alice'], [2, 'Bob']] },
    ])

    const { executeQuery } = useSqlite()
    const result = await executeQuery(1, 'SELECT * FROM users')

    expect(result.columns).toEqual(['id', 'name'])
    expect(result.rows).toEqual([[1, 'Alice'], [2, 'Bob']])
  })

  it('executeQuery returns empty result when db.exec returns nothing', async () => {
    mockExec.mockReturnValue([])

    const { executeQuery } = useSqlite()
    const result = await executeQuery(1, 'SELECT * FROM empty')

    expect(result.columns).toEqual([])
    expect(result.rows).toEqual([])
  })

  it('clearCache with connectionId closes and removes specific entry', async () => {
    const { getDatabase, clearCache } = useSqlite()

    await getDatabase(5)
    clearCache(5)

    expect(mockClose).toHaveBeenCalledTimes(1)

    // Fetching again should hit the network, not the cache
    mockGetSqliteUrl.mockClear()
    ;(globalThis.fetch as ReturnType<typeof vi.fn>).mockClear()
    await getDatabase(5)
    expect(mockGetSqliteUrl).toHaveBeenCalledTimes(1)
  })

  it('clearCache with no args closes and removes all entries', async () => {
    const { getDatabase, clearCache } = useSqlite()

    await getDatabase(1)
    await getDatabase(2)

    mockClose.mockClear()
    clearCache()

    expect(mockClose).toHaveBeenCalledTimes(2)

    // Fetching again should hit the network
    mockGetSqliteUrl.mockClear()
    await getDatabase(1)
    expect(mockGetSqliteUrl).toHaveBeenCalledTimes(1)
  })
})
