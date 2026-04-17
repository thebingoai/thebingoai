// @ts-nocheck — ref/computed/useApi are Nuxt auto-imports; .nuxt types only exist inside Docker
export interface MentionItem {
  type: 'dashboard' | 'connection'
  id: number
  name: string        // slugified token used in @mention text
  displayName: string // original label shown in panel
  dbType?: string     // connections only
}

interface MentionsState {
  isMentionOpen: ReturnType<typeof ref<boolean>>
  mentionQuery: ReturnType<typeof ref<string>>
  mentionAnchor: ReturnType<typeof ref<number>>
  resolvedMentions: ReturnType<typeof ref<Map<string, MentionItem>>>
  dashboardsCache: ReturnType<typeof ref<MentionItem[]>>
  connectionsCache: ReturnType<typeof ref<MentionItem[]>>
  filteredResults: ReturnType<typeof computed<{ dashboards: MentionItem[]; connections: MentionItem[] }>>
}

// Module-level singleton holder — refs are created lazily inside useMentions()
// so that Nuxt auto-imports (ref, computed) resolve correctly.
let _state: MentionsState | null = null

const slugify = (s: string) =>
  s.toLowerCase().replace(/\s+/g, '-').replace(/[^\w.-]/g, '')

async function _doLoad(api: ReturnType<typeof useApi>, state: MentionsState) {
  const [dashRes, connRes] = await Promise.all([
    api.dashboards.list().catch(() => null),
    api.connections.list().catch(() => null),
  ])

  const dashboards: any[] = Array.isArray(dashRes)
    ? dashRes
    : (dashRes as any)?.dashboards ?? []

  const connections: any[] = Array.isArray(connRes)
    ? connRes
    : (connRes as any)?.connections ?? []

  state.dashboardsCache.value = dashboards.map((d: any) => ({
    type: 'dashboard' as const,
    id: d.id,
    name: slugify(d.title || ''),
    displayName: d.title || '',
  }))

  state.connectionsCache.value = connections.map((c: any) => ({
    type: 'connection' as const,
    id: c.id,
    name: slugify(c.name || ''),
    displayName: c.name || '',
    dbType: c.db_type,
  }))
}

export const useMentions = () => {
  const api = useApi()

  // Initialise singleton state on first call (refs/computed need composable context)
  if (!_state) {
    const isMentionOpen = ref(false)
    const mentionQuery = ref('')
    const mentionAnchor = ref(-1)
    const resolvedMentions = ref(new Map<string, MentionItem>())
    const dashboardsCache = ref<MentionItem[]>([])
    const connectionsCache = ref<MentionItem[]>([])

    const filteredResults = computed(() => {
      const q = mentionQuery.value.toLowerCase()
      const matches = (item: MentionItem) =>
        !q || item.displayName.toLowerCase().includes(q) || item.name.includes(q)
      return {
        dashboards: dashboardsCache.value.filter(matches),
        connections: connectionsCache.value.filter(matches),
      }
    })

    _state = { isMentionOpen, mentionQuery, mentionAnchor, resolvedMentions, dashboardsCache, connectionsCache, filteredResults }
  }

  const state = _state

  const openMention = (anchorPos: number) => {
    state.mentionAnchor.value = anchorPos
    state.isMentionOpen.value = true
    // Always re-fetch so newly created dashboards/connections appear immediately
    _doLoad(api, state)
  }

  const closeMention = () => {
    state.isMentionOpen.value = false
    state.mentionQuery.value = ''
  }

  const setQuery = (q: string) => {
    state.mentionQuery.value = q
  }

  const recordMention = (item: MentionItem) => {
    state.resolvedMentions.value.set(item.name, item)
  }

  // Returns connection IDs for @mentions found in text (dashboard mentions excluded)
  const extractMentionConnectionIds = (text: string): number[] => {
    const ids: number[] = []
    for (const m of text.matchAll(/@([\w.-]+)/g)) {
      const item = state.resolvedMentions.value.get(m[1])
      if (item?.type === 'connection') ids.push(item.id)
    }
    return ids
  }

  const clearResolvedMentions = () => {
    state.resolvedMentions.value = new Map()
  }

  return {
    isMentionOpen: state.isMentionOpen,
    mentionQuery: state.mentionQuery,
    mentionAnchor: state.mentionAnchor,
    filteredResults: state.filteredResults,
    openMention,
    closeMention,
    setQuery,
    recordMention,
    extractMentionConnectionIds,
    clearResolvedMentions,
  }
}
