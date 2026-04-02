import { describe, it, expect } from 'vitest'
import { cn } from '~/utils/cn'

describe('utils/cn', () => {
  it('merges basic class names', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('resolves conflicting tailwind classes (last wins)', () => {
    const result = cn('p-2', 'p-4')
    expect(result).toBe('p-4')
  })

  it('handles empty and falsy inputs gracefully', () => {
    expect(cn('', null, undefined, false, 'active')).toBe('active')
  })
})
