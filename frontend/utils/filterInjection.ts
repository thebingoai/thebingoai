export interface FilterParam {
  column: string
  op: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'ilike'
  value: any
}

const KEYWORD_PATTERN = /\b(GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|OFFSET)\b/i
const WHERE_PATTERN = /\bWHERE\b/i

const OP_MAP: Record<string, string> = {
  eq: '=',
  neq: '!=',
  gt: '>',
  gte: '>=',
  lt: '<',
  lte: '<=',
  ilike: 'LIKE',  // SQLite: use LIKE, not ILIKE
}

/**
 * Inject filter conditions into a SQL query for sql.js (SQLite).
 * Returns modified SQL with ? placeholders and a params array.
 * SQLite uses positional ? params, not named %(key)s params.
 */
export function injectFiltersForSqlite(sql: string, filters: FilterParam[]): { sql: string; params: any[] } {
  if (!filters.length) return { sql, params: [] }

  const params: any[] = []
  const conditions: string[] = []

  for (const f of filters) {
    const col = `"${f.column}"`
    const op = OP_MAP[f.op]
    if (f.op === 'ilike') {
      // SQLite LIKE is case-insensitive for ASCII by default, but to be safe:
      conditions.push(`LOWER(${col}) LIKE LOWER(?)`)
    } else {
      conditions.push(`${col} ${op} ?`)
    }
    params.push(f.value)
  }

  const conditionClause = conditions.join(' AND ')

  const whereMatch = WHERE_PATTERN.exec(sql)
  let modified: string

  if (whereMatch) {
    // Find where the next major keyword starts after WHERE
    const afterWhere = sql.slice(whereMatch.index + whereMatch[0].length)
    const keywordMatch = KEYWORD_PATTERN.exec(afterWhere)
    if (keywordMatch) {
      const insertPos = whereMatch.index + whereMatch[0].length + keywordMatch.index
      modified = sql.slice(0, insertPos).trimEnd() + ` AND ${conditionClause} ` + sql.slice(insertPos)
    } else {
      modified = sql.trimEnd() + ` AND ${conditionClause}`
    }
  } else {
    const keywordMatch = KEYWORD_PATTERN.exec(sql)
    if (keywordMatch) {
      const insertPos = keywordMatch.index
      modified = sql.slice(0, insertPos).trimEnd() + ` WHERE ${conditionClause} ` + sql.slice(insertPos)
    } else {
      modified = sql.trimEnd() + ` WHERE ${conditionClause}`
    }
  }

  return { sql: modified, params }
}
