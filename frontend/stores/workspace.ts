import { defineStore } from 'pinia'

export interface Workspace { org_id: string; org_name: string | null; role: string; is_home: boolean }

const LS_KEY = 'bingo.activeWorkspace'

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    activeOrgId: null as string | null,
    workspaces: [] as Workspace[],
  }),
  getters: {
    activeRole(state): string | null {
      const w = state.workspaces.find(w => w.org_id === state.activeOrgId)
      return w ? w.role : null
    },
    isViewer(): boolean { return this.activeRole === 'viewer' },
  },
  actions: {
    hydrate() {
      if (typeof window !== 'undefined') this.activeOrgId = localStorage.getItem(LS_KEY)
    },
    setActive(orgId: string | null) {
      this.activeOrgId = orgId
      if (typeof window !== 'undefined') {
        if (orgId) localStorage.setItem(LS_KEY, orgId)
        else localStorage.removeItem(LS_KEY)
      }
    },
    setWorkspaces(ws: Workspace[]) { this.workspaces = ws },
    // Adopt a freshly-fetched workspace list. A persisted org the account has no
    // membership in — a stale id left by a previous session on this tab — leaves
    // `activeRole` null, which makes `isViewer` false and un-hides the
    // workspace-admin settings sections. Drop it, then fall back to the home
    // workspace.
    reconcile(ws: Workspace[]) {
      this.setWorkspaces(ws)
      if (this.activeOrgId && !ws.some(w => w.org_id === this.activeOrgId)) this.setActive(null)
      if (!this.activeOrgId) {
        const home = ws.find(w => w.is_home) || ws[0]
        if (home) this.setActive(home.org_id)
      }
    },
  },
})
