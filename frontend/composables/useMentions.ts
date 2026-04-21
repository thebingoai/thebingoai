// @ts-nocheck — ref/computed/useApi are Nuxt auto-imports; .nuxt types only exist inside Docker
export interface MentionItem {
  type: 'dashboard' | 'connection' | 'notion_page'
  id: number
  name: string           // slugified token used in @mention text
  displayName: string    // original label shown in panel
  dbType?: string        // connections only
  pageId?: string        // notion_page only: Notion page UUID
  connectionId?: number  // notion_page only: parent connection id
}

export interface MentionGroup {
  id: string             // 'dashboards' | 'databases' | 'notion:{connId}'
  label: string          // display name for the group
  subLabel: string       // e.g. '3 dashboards', 'notion'
  iconType: 'dashboard' | 'database' | 'notion'
  count: number
  items: MentionItem[]
}

interface MentionsState {
  isMentionOpen: ReturnType<typeof ref<boolean>>
  mentionQuery: ReturnType<typeof ref<string>>
  mentionAnchor: ReturnType<typeof ref<number>>
  mentionLevel: ReturnType<typeof ref<'root' | 'items'>>
  activeGroupId: ReturnType<typeof ref<string | null>>
  resolvedMentions: ReturnType<typeof ref<Map<string, MentionItem>>>
  dashboardsCache: ReturnType<typeof ref<MentionItem[]>>
  connectionsCache: ReturnType<typeof ref<MentionItem[]>>
  notionPagesCache: ReturnType<typeof ref<MentionItem[]>>
  notionSyncHint: ReturnType<typeof ref<string>>
  notionConnectionNames: ReturnType<typeof ref<Map<number, string>>>
  mentionGroups: ReturnType<typeof computed<MentionGroup[]>>
  filteredGroups: ReturnType<typeof computed<MentionGroup[]>>
  activeGroupItems: ReturnType<typeof computed<MentionItem[]>>
  activeGroup: ReturnType<typeof computed<MentionGroup | null>>
}

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

  // Fetch pages from all Notion connections
  const notionConnections = connections.filter((c: any) => c.db_type === 'notion')

  // Build connection name map for group labels
  const nameMap = new Map<number, string>()
  for (const c of notionConnections) nameMap.set(c.id, c.name || 'Notion')
  state.notionConnectionNames.value = nameMap

  const pageResults = await Promise.all(
    notionConnections.map((c: any) =>
      api.notion.listPages(c.id).catch(() => ({ pages: [], synced: false, synced_page_count: 0 }))
    )
  )

  const notionPages: MentionItem[] = []
  let syncHint = ''
  notionConnections.forEach((conn: any, i: number) => {
    const result = pageResults[i]
    for (const page of result.pages) {
      if (!page.title) continue
      notionPages.push({
        type: 'notion_page' as const,
        id: conn.id,
        name: `notion-${slugify(page.title)}`,
        displayName: page.title,
        pageId: page.id,
        connectionId: conn.id,
      })
    }
    if (result.synced && result.pages.length === 0 && !syncHint) {
      syncHint = 'No Notion pages found — share pages with your integration in Notion, then Sync Now.'
    }
  })
  state.notionPagesCache.value = notionPages
  state.notionSyncHint.value = syncHint
}

export const useMentions = () => {
  const api = useApi()

  if (!_state) {
    const isMentionOpen = ref(false)
    const mentionQuery = ref('')
    const mentionAnchor = ref(-1)
    const mentionLevel = ref<'root' | 'items'>('root')
    const activeGroupId = ref<string | null>(null)
    const resolvedMentions = ref(new Map<string, MentionItem>())
    const dashboardsCache = ref<MentionItem[]>([])
    const connectionsCache = ref<MentionItem[]>([])
    const notionPagesCache = ref<MentionItem[]>([])
    const notionSyncHint = ref('')
    const notionConnectionNames = ref(new Map<number, string>())

    // Build groups from cached data
    const mentionGroups = computed((): MentionGroup[] => {
      const groups: MentionGroup[] = []

      if (dashboardsCache.value.length > 0) {
        groups.push({
          id: 'dashboards',
          label: 'Dashboards',
          subLabel: `${dashboardsCache.value.length} dashboard${dashboardsCache.value.length !== 1 ? 's' : ''}`,
          iconType: 'dashboard',
          count: dashboardsCache.value.length,
          items: dashboardsCache.value,
        })
      }

      const dbConns = connectionsCache.value.filter(c => c.dbType !== 'notion')
      if (dbConns.length > 0) {
        groups.push({
          id: 'databases',
          label: 'Databases',
          subLabel: `${dbConns.length} connection${dbConns.length !== 1 ? 's' : ''}`,
          iconType: 'database',
          count: dbConns.length,
          items: dbConns,
        })
      }

      // One group per Notion connection
      const notionConnIds = [...new Set(notionPagesCache.value.map(p => p.connectionId!))]
      for (const connId of notionConnIds) {
        const pages = notionPagesCache.value.filter(p => p.connectionId === connId)
        const name = notionConnectionNames.value.get(connId) || 'Notion'
        groups.push({
          id: `notion:${connId}`,
          label: name,
          subLabel: `${pages.length} page${pages.length !== 1 ? 's' : ''}`,
          iconType: 'notion',
          count: pages.length,
          items: pages,
        })
      }

      // If Notion connections exist but no pages yet, still show the group (with hint)
      const notionConns = connectionsCache.value.filter(c => c.dbType === 'notion')
      for (const conn of notionConns) {
        const alreadyAdded = notionConnIds.includes(conn.id)
        if (!alreadyAdded) {
          groups.push({
            id: `notion:${conn.id}`,
            label: notionConnectionNames.value.get(conn.id) || conn.displayName || 'Notion',
            subLabel: '0 pages',
            iconType: 'notion',
            count: 0,
            items: [],
          })
        }
      }

      return groups
    })

    const filteredGroups = computed((): MentionGroup[] => {
      const q = mentionQuery.value.toLowerCase().trim()
      if (!q) return mentionGroups.value
      return mentionGroups.value.filter(g =>
        g.label.toLowerCase().includes(q) || g.subLabel.toLowerCase().includes(q)
      )
    })

    const activeGroup = computed((): MentionGroup | null => {
      if (!activeGroupId.value) return null
      return mentionGroups.value.find(g => g.id === activeGroupId.value) ?? null
    })

    const activeGroupItems = computed((): MentionItem[] => {
      const group = activeGroup.value
      if (!group) return []
      const q = mentionQuery.value.toLowerCase().trim()
      if (!q) return group.items
      return group.items.filter(item =>
        item.displayName.toLowerCase().includes(q) || item.name.includes(q)
      )
    })

    _state = {
      isMentionOpen, mentionQuery, mentionAnchor, mentionLevel, activeGroupId,
      resolvedMentions, dashboardsCache, connectionsCache, notionPagesCache,
      notionSyncHint, notionConnectionNames,
      mentionGroups, filteredGroups, activeGroup, activeGroupItems,
    }
  }

  const state = _state

  const openMention = (anchorPos: number) => {
    state.mentionAnchor.value = anchorPos
    state.isMentionOpen.value = true
    state.mentionLevel.value = 'root'
    state.activeGroupId.value = null
    state.mentionQuery.value = ''
    _doLoad(api, state)
  }

  const closeMention = () => {
    state.isMentionOpen.value = false
    state.mentionQuery.value = ''
    state.mentionLevel.value = 'root'
    state.activeGroupId.value = null
  }

  const setQuery = (q: string) => {
    state.mentionQuery.value = q
  }

  const drillIntoGroup = (groupId: string) => {
    state.activeGroupId.value = groupId
    state.mentionLevel.value = 'items'
    state.mentionQuery.value = ''
  }

  const goBackToRoot = () => {
    state.mentionLevel.value = 'root'
    state.activeGroupId.value = null
    state.mentionQuery.value = ''
  }

  const recordMention = (item: MentionItem) => {
    state.resolvedMentions.value.set(item.name, item)
  }

  const extractMentionConnectionIds = (text: string): number[] => {
    const ids: number[] = []
    for (const m of text.matchAll(/@([\w.-]+)/g)) {
      const item = state.resolvedMentions.value.get(m[1])
      if (item?.type === 'connection') ids.push(item.id)
      else if (item?.type === 'notion_page' && item.connectionId) ids.push(item.connectionId)
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
    mentionLevel: state.mentionLevel,
    notionSyncHint: state.notionSyncHint,
    filteredGroups: state.filteredGroups,
    activeGroup: state.activeGroup,
    activeGroupItems: state.activeGroupItems,
    openMention,
    closeMention,
    setQuery,
    drillIntoGroup,
    goBackToRoot,
    recordMention,
    extractMentionConnectionIds,
    clearResolvedMentions,
  }
}
