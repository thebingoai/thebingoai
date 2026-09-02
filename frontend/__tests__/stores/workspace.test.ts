import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useWorkspaceStore } from '~/stores/workspace'

describe('workspace store', () => {
  beforeEach(() => { setActivePinia(createPinia()); localStorage.clear() })

  it('persists active workspace id to localStorage', () => {
    const s = useWorkspaceStore()
    s.setActive('org-123')
    expect(s.activeOrgId).toBe('org-123')
    expect(localStorage.getItem('bingo.activeWorkspace')).toBe('org-123')
  })

  it('hydrates from localStorage', () => {
    localStorage.setItem('bingo.activeWorkspace', 'org-xyz')
    const s = useWorkspaceStore()
    s.hydrate()
    expect(s.activeOrgId).toBe('org-xyz')
  })

  it('isViewer reflects active role', () => {
    const s = useWorkspaceStore()
    s.setWorkspaces([{ org_id: 'o1', org_name: 'O1', role: 'viewer', is_home: false }])
    s.setActive('o1')
    expect(s.isViewer).toBe(true)
  })

  // ── reconcile ──────────────────────────────────────────────────────
  //
  // The active org is persisted, so it outlives the account that chose it if a
  // session ends without clearing. An id the fetched list does not contain leaves
  // `activeRole` null — which makes `isViewer` false and un-hides the
  // workspace-admin settings sections — and pins the switcher to a workspace this
  // user has no membership in.

  it('reconcile drops a persisted org the account is not a member of', () => {
    localStorage.setItem('bingo.activeWorkspace', 'org-from-previous-account')
    const s = useWorkspaceStore()
    s.hydrate()

    s.reconcile([
      { org_id: 'o1', org_name: 'O1', role: 'member', is_home: false },
      { org_id: 'home', org_name: 'Home', role: 'admin', is_home: true },
    ])

    expect(s.activeOrgId).toBe('home')
    expect(localStorage.getItem('bingo.activeWorkspace')).toBe('home')
    expect(s.activeRole).toBe('admin')
  })

  it('reconcile keeps a persisted org that is still in the list', () => {
    localStorage.setItem('bingo.activeWorkspace', 'o1')
    const s = useWorkspaceStore()
    s.hydrate()

    s.reconcile([
      { org_id: 'o1', org_name: 'O1', role: 'viewer', is_home: false },
      { org_id: 'home', org_name: 'Home', role: 'admin', is_home: true },
    ])

    expect(s.activeOrgId).toBe('o1')
    expect(s.isViewer).toBe(true)
  })

  it('reconcile falls back to the first workspace when none is flagged home', () => {
    const s = useWorkspaceStore()
    s.reconcile([
      { org_id: 'first', org_name: 'First', role: 'member', is_home: false },
      { org_id: 'second', org_name: 'Second', role: 'member', is_home: false },
    ])
    expect(s.activeOrgId).toBe('first')
  })

  it('reconcile on an empty list leaves nothing active', () => {
    localStorage.setItem('bingo.activeWorkspace', 'org-gone')
    const s = useWorkspaceStore()
    s.hydrate()

    expect(() => s.reconcile([])).not.toThrow()
    expect(s.activeOrgId).toBeNull()
    expect(localStorage.getItem('bingo.activeWorkspace')).toBeNull()
  })
})
