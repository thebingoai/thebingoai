// @ts-nocheck — ref/computed/useApi are Nuxt auto-imports; .nuxt types only exist inside Docker
export interface MentionItem {
  type: 'dashboard' | 'connection' | 'notion_page' | 'notion_database'
  id: number
  name: string           // slugified token used in @mention text
  displayName: string    // original label shown in panel
  dbType?: string        // connections only
  pageId?: string        // notion_page only: Notion page UUID
  databaseId?: string    // notion_database only: Notion database UUID
  connectionId?: number  // notion_page / notion_database: parent connection id
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
  notionDatabasesCache: ReturnType<typeof ref<MentionItem[]>>
  notionSyncHint: ReturnType<typeof ref<string>>
  notionConnectionNames: ReturnType<typeof ref<Map<number, string>>>
  mentionGroups: ReturnType<typeof computed<MentionGroup[]>>
  filteredGroups: ReturnType<typeof computed<MentionGroup[]>>
  activeGroupItems: ReturnType<typeof computed<MentionItem[]>>
  activeGroup: ReturnType<typeof computed<MentionGroup | null>>
  scopedPill: ReturnType<typeof ref<HTMLElement | null>>
  isChildMode: ReturnType<typeof ref<boolean>>
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

  const [pageResults, dbResults] = await Promise.all([
    Promise.all(
      notionConnections.map((c: any) =>
        api.notion.listPages(c.id).catch(() => ({ pages: [], synced: false, synced_page_count: 0 }))
      )
    ),
    Promise.all(
      notionConnections.map((c: any) =>
        (api.notion.listDatabases ? api.notion.listDatabases(c.id) : Promise.resolve({ databases: [] }))
          .catch(() => ({ databases: [] }))
      )
    ),
  ])

  const notionPages: MentionItem[] = []
  const notionDatabases: MentionItem[] = []
  let syncHint = ''
  notionConnections.forEach((conn: any, i: number) => {
    const pageResult = pageResults[i]
    const dbResult = dbResults[i]

    for (const page of pageResult.pages) {
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

    for (const db of (dbResult.databases || [])) {
      if (!db.title) continue
      notionDatabases.push({
        type: 'notion_database' as const,
        id: conn.id,
        name: `notion-db-${slugify(db.title)}`,
        displayName: db.title,
        databaseId: db.id,
        connectionId: conn.id,
      })
    }

    if (pageResult.synced && pageResult.pages.length === 0 && (dbResult.databases || []).length === 0 && !syncHint) {
      syncHint = 'No Notion content found — share pages or databases with your integration in Notion, then Sync Now.'
    }
  })
  state.notionPagesCache.value = notionPages
  state.notionDatabasesCache.value = notionDatabases
  state.notionSyncHint.value = syncHint
}

// ── Selection save/restore for mention panel ───────────────
let savedRange: Range | null = null

function restoreSelectionRange(): boolean {
  if (!savedRange) return false
  const sel = window.getSelection()
  if (!sel) return false
  sel.removeAllRanges()
  sel.addRange(savedRange)
  savedRange = null
  return true
}

// ── Pill editing for parent/child — module-level avoids reactivity issues ─
let editingPill: HTMLElement | null = null

function getEditingPill(): HTMLElement | null {
  return editingPill
}

function clearEditingPill() {
  editingPill = null
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
    const notionDatabasesCache = ref<MentionItem[]>([])
    const notionSyncHint = ref('')
    const notionConnectionNames = ref(new Map<number, string>())
    const scopedPill = ref<HTMLElement | null>(null)
    const isChildMode = ref(false)

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

      // One group per Notion connection — merge pages + databases
      const notionConns = connectionsCache.value.filter(c => c.dbType === 'notion')
      for (const conn of notionConns) {
        const connId = conn.id
        const pages = notionPagesCache.value.filter(p => p.connectionId === connId)
        const dbs = notionDatabasesCache.value.filter(d => d.connectionId === connId)
        const allItems = [...dbs, ...pages]
        const name = notionConnectionNames.value.get(connId) || conn.displayName || 'Notion'

        let subLabel: string
        if (dbs.length > 0 && pages.length > 0) {
          subLabel = `${dbs.length} database${dbs.length !== 1 ? 's' : ''} · ${pages.length} page${pages.length !== 1 ? 's' : ''}`
        } else if (dbs.length > 0) {
          subLabel = `${dbs.length} database${dbs.length !== 1 ? 's' : ''}`
        } else if (pages.length > 0) {
          subLabel = `${pages.length} page${pages.length !== 1 ? 's' : ''}`
        } else {
          subLabel = '0 pages'
        }

        groups.push({
          id: `notion:${connId}`,
          label: name,
          subLabel,
          iconType: 'notion',
          count: allItems.length,
          items: allItems,
        })
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
      notionDatabasesCache, notionSyncHint, notionConnectionNames,
      mentionGroups, filteredGroups, activeGroup, activeGroupItems,
      scopedPill, isChildMode,
    }
  }

  const state = _state

  const openMention = (anchorPos: number) => {
    // Save cursor selection so handleMentionSelect can find the @ position
    try { savedRange = window.getSelection()?.getRangeAt(0) ?? null } catch { savedRange = null }
    clearEditingPill()
    state.isChildMode.value = false
    state.mentionAnchor.value = anchorPos
    state.isMentionOpen.value = true
    state.mentionLevel.value = 'root'
    state.activeGroupId.value = null
    state.mentionQuery.value = ''
    _doLoad(api, state)
  }

  const openMentionForPill = (pillEl: HTMLElement) => {
    editingPill = pillEl
    state.isChildMode.value = true
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
    clearEditingPill()
    state.isChildMode.value = false
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
      else if ((item?.type === 'notion_page' || item?.type === 'notion_database') && item.connectionId) ids.push(item.connectionId)
    }
    return ids
  }

  // Resolved @-mentions in the message, in order, with the structured payload
  // expected by ChatRequest.mentions on the backend.
  const extractMentions = (text: string): Array<{
    type: 'dashboard' | 'connection' | 'notion_page'
    id: number
    name: string
    display_name: string
    db_type?: string
    page_id?: string
    connection_id?: number
  }> => {
    const out: Array<any> = []
    const seen = new Set<string>()
    for (const m of text.matchAll(/@([\w.-]+)/g)) {
      const slug = m[1]
      if (seen.has(slug)) continue
      const item = state.resolvedMentions.value.get(slug)
      if (!item) continue
      seen.add(slug)
      out.push({
        type: item.type,
        id: item.id,
        name: item.name,
        display_name: item.displayName,
        db_type: item.dbType,
        page_id: item.pageId,
        database_id: item.databaseId,
        connection_id: item.connectionId,
      })
    }
    return out
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
    resolvedMentions: state.resolvedMentions,
    isChildMode: state.isChildMode,
    openMention,
    openMentionForPill,
    closeMention,
    setQuery,
    drillIntoGroup,
    goBackToRoot,
    recordMention,
    extractMentionConnectionIds,
    extractMentions,
    clearResolvedMentions,
    restoreSelectionRange,
    getEditingPill,
  }
}
