import { describe, it, expect } from 'vitest'
import { resolveLegacyTab, canonicalizeTabQuery } from '~/utils/settingsLegacyTabs'

describe('resolveLegacyTab', () => {
  it('sends the retired members tabs to the People sub-tab, not just the page', () => {
    // Without the sub, People opens on whichever sub-tab comes first — Active,
    // for a platform admin — so a Members bookmark showed the wrong table.
    expect(resolveLegacyTab('org-members')).toEqual({ tab: 'people', sub: 'members' })
    expect(resolveLegacyTab('members')).toEqual({ tab: 'people', sub: 'members' })
  })

  it('sends the other merged ids to People with no sub-tab preference', () => {
    expect(resolveLegacyTab('users')).toEqual({ tab: 'people' })
    expect(resolveLegacyTab('invitations')).toEqual({ tab: 'people' })
  })

  it('sends the removed workspace-credits tab to the account Credits section', () => {
    expect(resolveLegacyTab('org-credits')).toEqual({ tab: 'credits' })
  })

  it('leaves current tab ids alone', () => {
    for (const id of ['people', 'credits', 'agent', 'audit-log', 'nonsense']) {
      expect(resolveLegacyTab(id)).toBeNull()
    }
  })

  it('never maps a target onto another legacy id (a redirect loop)', () => {
    for (const raw of ['users', 'members', 'invitations', 'org-members', 'org-credits']) {
      const target = resolveLegacyTab(raw)!
      expect(resolveLegacyTab(target.tab)).toBeNull()
    }
  })
})

describe('canonicalizeTabQuery', () => {
  it('rewrites the tab and applies the target sub', () => {
    expect(canonicalizeTabQuery({ tab: 'org-members' }, { tab: 'people', sub: 'members' }))
      .toEqual({ tab: 'people', sub: 'members' })
  })

  it('drops a stale sub when the target names none', () => {
    expect(canonicalizeTabQuery({ tab: 'org-credits', sub: 'members' }, { tab: 'credits' }))
      .toEqual({ tab: 'credits' })
  })

  it('preserves unrelated query params', () => {
    expect(canonicalizeTabQuery({ tab: 'org-members', foo: 'bar' }, { tab: 'people', sub: 'members' }))
      .toEqual({ tab: 'people', sub: 'members', foo: 'bar' })
  })

  it('does not mutate the input query', () => {
    const query = { tab: 'org-credits', sub: 'members' }
    canonicalizeTabQuery(query, { tab: 'credits' })
    expect(query).toEqual({ tab: 'org-credits', sub: 'members' })
  })
})
