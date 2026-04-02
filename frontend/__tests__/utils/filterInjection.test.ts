import { describe, it, expect } from 'vitest'
import { injectFiltersForSqlite, type FilterParam } from '~/utils/filterInjection'

describe('utils/filterInjection', () => {
  it('returns original SQL unchanged when filters are empty', () => {
    const sql = 'SELECT * FROM users'
    const result = injectFiltersForSqlite(sql, [])
    expect(result.sql).toBe(sql)
    expect(result.params).toEqual([])
  })

  it('adds a WHERE clause for a single eq filter', () => {
    const sql = 'SELECT * FROM users'
    const filters: FilterParam[] = [{ column: 'name', op: 'eq', value: 'Alice' }]
    const result = injectFiltersForSqlite(sql, filters)
    expect(result.sql).toContain('WHERE')
    expect(result.sql).toContain('"name" = ?')
    expect(result.params).toEqual(['Alice'])
  })

  it('uses LOWER() wrapping for ilike filter', () => {
    const sql = 'SELECT * FROM users'
    const filters: FilterParam[] = [{ column: 'email', op: 'ilike', value: '%test%' }]
    const result = injectFiltersForSqlite(sql, filters)
    expect(result.sql).toContain('LOWER("email") LIKE LOWER(?)')
    expect(result.params).toEqual(['%test%'])
  })

  it('joins multiple filters with AND', () => {
    const sql = 'SELECT * FROM products'
    const filters: FilterParam[] = [
      { column: 'price', op: 'gt', value: 10 },
      { column: 'stock', op: 'lt', value: 100 },
    ]
    const result = injectFiltersForSqlite(sql, filters)
    expect(result.sql).toContain('"price" > ?')
    expect(result.sql).toContain('AND')
    expect(result.sql).toContain('"stock" < ?')
    expect(result.params).toEqual([10, 100])
  })

  it('appends AND to an existing WHERE clause', () => {
    const sql = 'SELECT * FROM orders WHERE status = 1'
    const filters: FilterParam[] = [{ column: 'total', op: 'gte', value: 50 }]
    const result = injectFiltersForSqlite(sql, filters)
    expect(result.sql).toContain('WHERE status = 1')
    expect(result.sql).toContain('AND "total" >= ?')
    expect(result.params).toEqual([50])
  })

  it('inserts filter before GROUP BY', () => {
    const sql = 'SELECT category, COUNT(*) FROM products GROUP BY category'
    const filters: FilterParam[] = [{ column: 'active', op: 'eq', value: 1 }]
    const result = injectFiltersForSqlite(sql, filters)
    expect(result.sql).toMatch(/WHERE "active" = \?.*GROUP BY/s)
    expect(result.params).toEqual([1])
  })

  it('inserts filter before ORDER BY', () => {
    const sql = 'SELECT * FROM logs ORDER BY created_at DESC'
    const filters: FilterParam[] = [{ column: 'level', op: 'eq', value: 'error' }]
    const result = injectFiltersForSqlite(sql, filters)
    expect(result.sql).toMatch(/WHERE "level" = \?.*ORDER BY/s)
    expect(result.params).toEqual(['error'])
  })

  it('params array matches filter values in order', () => {
    const sql = 'SELECT * FROM data'
    const filters: FilterParam[] = [
      { column: 'a', op: 'eq', value: 'first' },
      { column: 'b', op: 'neq', value: 'second' },
      { column: 'c', op: 'lte', value: 99 },
    ]
    const result = injectFiltersForSqlite(sql, filters)
    expect(result.params).toEqual(['first', 'second', 99])
  })
})
