// Memory cache: connectionId → { db: Database, loadedAt: number }
const _dbCache = new Map<number, { db: any; loadedAt: number }>()
const CACHE_TTL_MS = 60 * 60 * 1000 // 1 hour

let _sqlJsInitPromise: Promise<any> | null = null

async function _initSqlJs(): Promise<any> {
  if (_sqlJsInitPromise) return _sqlJsInitPromise
  _sqlJsInitPromise = import('sql.js').then(mod => {
    const initSqlJs = mod.default
    return initSqlJs({
      // The WASM file will be loaded from the CDN or local public dir
      locateFile: (filename: string) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.12.0/${filename}`
    })
  })
  return _sqlJsInitPromise
}

export interface SqliteQueryResult {
  columns: string[]
  rows: any[][]
}

export function useSqlite() {
  async function getDatabase(connectionId: number): Promise<any> {
    const cached = _dbCache.get(connectionId)
    if (cached && Date.now() - cached.loadedAt < CACHE_TTL_MS) {
      return cached.db
    }

    // Fetch presigned URL from backend
    const api = useApi()
    const { url } = await api.dashboards.getSqliteUrl(connectionId) as { url: string; expires_in: number }

    // Download SQLite file
    const response = await fetch(url)
    if (!response.ok) throw new Error(`Failed to download SQLite file: ${response.statusText}`)
    const buffer = await response.arrayBuffer()

    // Initialize sql.js and create database
    const SQL = await _initSqlJs()
    const db = new SQL.Database(new Uint8Array(buffer))

    _dbCache.set(connectionId, { db, loadedAt: Date.now() })
    return db
  }

  async function executeQuery(connectionId: number, sql: string, params?: any[]): Promise<SqliteQueryResult> {
    const db = await getDatabase(connectionId)
    const results = db.exec(sql, params)

    if (!results.length) {
      return { columns: [], rows: [] }
    }

    const { columns, values } = results[0]
    return { columns, rows: values }
  }

  function clearCache(connectionId?: number) {
    if (connectionId !== undefined) {
      const cached = _dbCache.get(connectionId)
      if (cached) {
        cached.db.close()
        _dbCache.delete(connectionId)
      }
    } else {
      _dbCache.forEach(({ db }) => db.close())
      _dbCache.clear()
    }
  }

  return { getDatabase, executeQuery, clearCache }
}
