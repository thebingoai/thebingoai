<template>
  <!-- Floating panel — positioned by parent (ChatInputBar) -->
  <div
    class="mention-panel"
    @mousedown.prevent
  >
    <!-- ── Header ─────────────────────────────────────────── -->
    <div class="mention-header">
      <!--
        The search input is ALWAYS in the DOM so keyboard events keep firing
        in both root and drill states. It's visually hidden in drill mode.
      -->
      <input
        ref="searchRef"
        v-model="localQuery"
        @keydown="handleKeydown"
        placeholder="type to filter"
        :class="props.mentionLevel === 'root' ? 'mention-query-input' : 'mention-query-input-hidden'"
        autocomplete="off"
        spellcheck="false"
      />

      <!-- Root: @ icon + query label (visual only — input above handles value) -->
      <template v-if="props.mentionLevel === 'root'">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--ember)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;margin-right:-4px">
          <circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-4 8"/>
        </svg>
        <span class="mention-header-at" style="margin-right:-2px">@</span>
        <span style="font-size:0"><!-- spacer --></span>
        <span class="mention-count">{{ totalItems }} match{{ totalItems !== 1 ? 'es' : '' }}</span>
      </template>

      <!-- Drill: ← esc + breadcrumb -->
      <template v-else>
        <button class="mention-esc-btn" @click="handleBack">
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="transform:rotate(180deg)"><polyline points="9 18 15 12 9 6"/></svg>
          esc
        </button>
        <div class="mention-breadcrumb">
          <span class="mention-bc-dim">@</span>
          <span class="mention-bc-dim">{{ kindMeta(activeGroupType).label.toLowerCase() }}</span>
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          <component :is="groupIconComponent(activeGroupType)" class="mention-bc-icon" />
          <span class="mention-bc-bold">{{ props.activeGroup?.label }}</span>
          <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
          <span class="mention-bc-italic">pick a child…</span>
        </div>
        <span class="mention-count">{{ props.activeGroupItems.length }} children</span>
      </template>
    </div>

    <!-- ── Filter chips (root only) ──────────────────────── -->
    <div v-if="props.mentionLevel === 'root'" class="mention-filters">
      <button
        v-for="chip in filterChips"
        :key="chip.id"
        class="mention-filter-chip"
        :class="{ active: filterKind === chip.id }"
        @click="filterKind = chip.id"
        @mousedown.prevent
      >{{ chip.label }}</button>
    </div>

    <!-- ── Body list ──────────────────────────────────────── -->
    <div class="mention-body" ref="bodyRef">

      <!-- ROOT: one row per group, grouped by kind (icon type) -->
      <template v-if="props.mentionLevel === 'root'">
        <!-- Group by iconType for the colored eyebrow headers -->
        <template v-for="(typeGroups, iconType) in groupedByType" :key="iconType">
          <!-- Kind eyebrow -->
          <div class="mention-group-label" :style="{ color: kindMeta(iconType).color }">
            {{ kindMeta(iconType).label }}
          </div>
          <!-- One row per group within this type -->
          <button
            v-for="group in typeGroups"
            :key="group.id"
            class="mention-row"
            :class="{ selected: flatGroupIndex(group.id) === activeIndex }"
            @click="selectGroup(group)"
          >
            <div
              class="mention-row-icon"
              :style="{
                background: kindMeta(iconType).wash,
                color: kindMeta(iconType).color,
                borderColor: `color-mix(in oklch, ${kindMeta(iconType).color} 20%, var(--line))`,
              }"
            >
              <component :is="groupIconComponent(iconType)" style="width:12px;height:12px" />
            </div>
            <div class="mention-row-text">
              <div class="mention-row-label">{{ group.label }}</div>
              <div class="mention-row-sub">{{ group.subLabel }}</div>
            </div>
            <!-- Child count + chevron -->
            <div class="mention-row-right">
              <span class="mention-child-count">{{ group.count }}</span>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="var(--ink-3)" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
            </div>
          </button>
        </template>

        <div v-if="visibleGroups.length === 0" class="mention-empty">No matches</div>
      </template>

      <!-- DRILL: flat children list -->
      <template v-else>
        <button
          v-for="(item, i) in props.activeGroupItems"
          :key="`child-${i}`"
          class="mention-row"
          :class="{ selected: i === activeIndex }"
          @click="emit('select', item)"
        >
          <div
            class="mention-row-icon"
            :style="{
              background: kindMeta(activeGroupType).wash,
              color: kindMeta(activeGroupType).color,
              borderColor: `color-mix(in oklch, ${kindMeta(activeGroupType).color} 20%, var(--line))`,
            }"
          >
            <component :is="childIconComponent(item)" style="width:12px;height:12px" />
          </div>
          <div class="mention-row-text">
            <div class="mention-row-label" :class="{ mono: true }">{{ item.displayName }}</div>
            <div class="mention-row-sub">{{ item.dbType ?? '' }}</div>
          </div>
          <span v-if="i === activeIndex" class="mention-tag-hint">↵ tag</span>
        </button>

        <div v-if="props.activeGroupItems.length === 0" class="mention-empty">No items</div>
      </template>
    </div>

    <!-- ── Footer keyboard hints ─────────────────────────── -->
    <div class="mention-footer">
      <span class="kbd-hint"><span class="kbd">↑↓</span> navigate</span>
      <span class="kbd-hint"><span class="kbd">↵</span> {{ props.mentionLevel === 'items' ? 'tag child' : 'tag' }}</span>
      <span class="kbd-hint"><span class="kbd">→</span> {{ props.mentionLevel === 'items' ? 'tag with child' : 'drill in' }}</span>
      <span class="kbd-hint"><span class="kbd">esc</span> {{ props.mentionLevel === 'items' ? 'back' : 'close' }}</span>
      <div style="flex:1" />
      <span class="kbd-tab-hint">tab · switch filter</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Database, LayoutDashboard, FileText, Zap, MessageSquare, Users, Table2, BarChart2, Settings2 } from 'lucide-vue-next'
import { h } from 'vue'
import type { MentionItem, MentionGroup } from '~/composables/useMentions'

const NotionIcon = markRaw({
  render() {
    return h('svg', { width: 12, height: 12, viewBox: '0 0 59.9 62.6' }, [
      h('path', { fill: '#FFFFFF', d: 'M3.8 2.7l34.6-2.6c4.2-.4 5.3-.1 8 1.8l11.1 7.8c1.8 1.3 2.4 1.7 2.4 3.2v42.7c0 2.7-1 4.3-4.4 4.5l-40.2 2.4c-2.6.1-3.8-.2-5.1-1.9L2.1 50.1c-1.5-2-2.1-3.4-2.1-5.1V7C0 4.8 1 2.9 3.8 2.7z' }),
      h('path', { 'fill-rule': 'evenodd', 'clip-rule': 'evenodd', d: 'M38.4.1L3.8 2.7C1 2.9 0 4.8 0 7v38c0 1.7.6 3.2 2.1 5.1l8.1 10.6c1.3 1.7 2.6 2.1 5.1 1.9l40.2-2.4c3.4-.2 4.4-1.8 4.4-4.5V12.9c0-1.4-.5-1.8-2.2-3l-.3-.2L46.4 2C43.8 0 42.7-.2 38.4.1zM16.2 12.2c-3.3.2-4 .3-5.9-1.3L5.6 7.2c-.5-.5-.3-1.1 1-1.2l33.3-2.4c2.8-.2 4.2.7 5.3 1.6l5.7 4.1c.3.1.9.8.1.8l-34.4 2.1-.4.1zM12.4 55.3V19c0-1.6.5-2.3 1.9-2.4l39.5-2.3c1.3-.1 1.9.7 1.9 2.3v36c0 1.6-.3 2.9-2.4 3l-37.8 2.2c-1.8.1-2.8-.7-2.8-2.6zm37.3-34.3c.2 1.1 0 2.2-1.1 2.3l-1.8.4v26.8c-1.6.9-3 1.3-4.2 1.3-1.9 0-2.4-.6-3.9-2.4L26.7 30.6v18.1l3.8.9s0 2.2-3 2.2l-8.4.5c-.2-.5 0-1.7.8-1.9l2.2-.6v-24l-3-.3c-.2-1.1.4-2.7 2.1-2.8l9-.6 12.4 19V24.3l-3.2-.4c-.2-1.3.7-2.3 1.9-2.4l5.7-.8z' }),
    ])
  },
})

const props = defineProps<{
  filteredGroups: MentionGroup[]
  activeGroup: MentionGroup | null
  activeGroupItems: MentionItem[]
  mentionLevel: 'root' | 'items'
}>()

const emit = defineEmits<{
  select: [item: MentionItem]
  close: []
  back: []
}>()

const searchRef = ref<HTMLInputElement | null>(null)
const bodyRef = ref<HTMLElement | null>(null)
const { mentionQuery, setQuery, drillIntoGroup, goBackToRoot } = useMentions()

// ── Local state ───────────────────────────────────────────────
const activeIndex = ref(0)
const filterKind = ref<'all' | string>('all')

// Keep local query in sync with composable
const localQuery = ref('')
watch(localQuery, (q) => setQuery(q))
watch(() => mentionQuery.value, (q) => { if (localQuery.value !== q) localQuery.value = q })
watch(() => props.mentionLevel, () => {
  activeIndex.value = 0
  localQuery.value = ''
  // Refocus the always-present input so keyboard events keep firing in drill mode
  nextTick(() => searchRef.value?.focus())
})
watch(() => props.filteredGroups.length, () => { activeIndex.value = 0 })
watch(() => props.activeGroupItems.length, () => { activeIndex.value = 0 })

onMounted(() => nextTick(() => searchRef.value?.focus()))

// ── Kind metadata ─────────────────────────────────────────────
const KIND_META: Record<string, { label: string; color: string; wash: string }> = {
  dashboard: { label: 'Dashboards', color: 'var(--d-teal)',  wash: 'color-mix(in oklch, var(--d-teal) 12%, var(--paper-0))' },
  database:  { label: 'Datasets',   color: 'var(--ember)',   wash: 'var(--ember-wash)' },
  notion:    { label: 'Notion',     color: '#2C2969',        wash: 'color-mix(in oklch, #2C2969 12%, var(--paper-0))' },
  skill:     { label: 'Skills',     color: 'var(--d-plum)',  wash: 'color-mix(in oklch, var(--d-plum) 14%, var(--paper-0))' },
  thread:    { label: 'Threads',    color: 'var(--ink-1)',   wash: 'var(--paper-2)' },
  person:    { label: 'People',     color: 'var(--d-moss)',  wash: 'color-mix(in oklch, var(--d-moss) 12%, var(--paper-0))' },
}

const kindMeta = (type: string) =>
  KIND_META[type] ?? { label: type, color: 'var(--ink-1)', wash: 'var(--paper-2)' }

function groupIconComponent(type: string) {
  if (type === 'dashboard') return LayoutDashboard
  if (type === 'database') return Database
  if (type === 'skill') return Zap
  if (type === 'thread') return MessageSquare
  if (type === 'person') return Users
  if (type === 'notion') return NotionIcon
  return FileText
}

function childIconComponent(item: MentionItem) {
  if (item.type === 'dashboard') return LayoutDashboard
  if (item.type === 'notion_page') return NotionIcon
  if (item.dbType === 'table') return Table2
  if (item.dbType === 'sheet') return Table2
  if (item.dbType === 'widget') return BarChart2
  if (item.dbType === 'param') return Settings2
  return Database
}

// ── Filter chips ──────────────────────────────────────────────
const filterChips = computed(() => {
  const types = [...new Set(props.filteredGroups.map(g => g.iconType))]
  return [
    { id: 'all', label: 'All' },
    ...types.map(t => ({ id: t, label: KIND_META[t]?.label ?? t })),
  ]
})

const activeGroupType = computed(() => props.activeGroup?.iconType ?? 'database')

const visibleGroups = computed(() => {
  const groups = props.filteredGroups
  if (filterKind.value === 'all') return groups
  return groups.filter(g => g.iconType === filterKind.value)
})

// Groups keyed by iconType — preserves insertion order for display
const groupedByType = computed(() => {
  const map: Record<string, typeof visibleGroups.value> = {}
  for (const g of visibleGroups.value) {
    if (!map[g.iconType]) map[g.iconType] = []
    map[g.iconType].push(g)
  }
  return map
})

// ── Index helpers ─────────────────────────────────────────────
const totalItems = computed(() =>
  props.mentionLevel === 'root' ? visibleGroups.value.length : props.activeGroupItems.length
)
const listLength = computed(() =>
  props.mentionLevel === 'root' ? visibleGroups.value.length : props.activeGroupItems.length
)

// Flat index of a group in visibleGroups (root level)
function flatGroupIndex(groupId: string): number {
  return visibleGroups.value.findIndex(g => g.id === groupId)
}

// ── Actions ───────────────────────────────────────────────────
function selectGroup(group: MentionGroup) {
  drillIntoGroup(group.id)
}

function handleBack() {
  goBackToRoot()
  emit('back')
}

function confirmSelection() {
  if (props.mentionLevel === 'root') {
    const group = visibleGroups.value[activeIndex.value]
    if (group) selectGroup(group)
  } else {
    const item = props.activeGroupItems[activeIndex.value]
    if (item) emit('select', item)
  }
}

function drillSelection() {
  if (props.mentionLevel === 'root') {
    const group = visibleGroups.value[activeIndex.value]
    if (group) selectGroup(group)
  }
}

// ── Keyboard ──────────────────────────────────────────────────
const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, listLength.value - 1)
    scrollToActive()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
    scrollToActive()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    drillSelection()
  } else if (e.key === 'Enter') {
    e.preventDefault()
    confirmSelection()
  } else if (e.key === 'Tab') {
    e.preventDefault()
    // Cycle filter
    const chips = filterChips.value
    const idx = chips.findIndex(c => c.id === filterKind.value)
    filterKind.value = chips[(idx + 1) % chips.length].id
  } else if (e.key === 'Escape') {
    e.preventDefault()
    if (props.mentionLevel === 'items') {
      handleBack()
    } else {
      emit('close')
    }
  } else if (e.key === 'Backspace' && !localQuery.value && props.mentionLevel === 'items') {
    handleBack()
  }
}

function scrollToActive() {
  nextTick(() => {
    const rows = bodyRef.value?.querySelectorAll('.mention-row')
    if (rows) rows[activeIndex.value]?.scrollIntoView({ block: 'nearest' })
  })
}
</script>

<style scoped>
/* ── Container ───────────────────────────────────────────────── */
.mention-panel {
  width: 460px;
  background: var(--paper-0);
  border: 1px solid var(--line-2);
  border-radius: 14px;
  box-shadow: 0 4px 12px rgba(17,17,19,0.06), 0 24px 60px rgba(17,17,19,0.18);
  overflow: hidden;
  font-family: var(--font-sans);
}

/* ── Header ──────────────────────────────────────────────────── */
.mention-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--line);
  background: var(--paper-1);
}
.mention-header-at {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--ember);
}
.mention-query-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-0);
  min-width: 0;
}
.mention-query-input::placeholder {
  font-weight: 400;
  color: var(--ink-3);
}
/* Always in DOM for keyboard events, invisible in drill mode */
.mention-query-input-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
  border: none;
  outline: none;
}
.mention-count {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--ink-3);
  flex-shrink: 0;
}

/* Breadcrumb */
.mention-esc-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border: 1px solid var(--line);
  background: var(--paper-0);
  padding: 2px 6px 2px 5px;
  border-radius: 5px;
  font-size: 10.5px;
  color: var(--ink-1);
  cursor: pointer;
  font-family: var(--font-sans);
  flex-shrink: 0;
}
.mention-breadcrumb {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.mention-bc-dim    { color: var(--ink-2); }
.mention-bc-bold   { color: var(--ink-0); font-family: var(--font-mono); font-weight: 600; }
.mention-bc-italic { color: var(--ink-2); font-style: italic; }
.mention-bc-icon   { width: 11px; height: 11px; flex-shrink: 0; }

/* ── Filter chips ─────────────────────────────────────────────── */
.mention-filters {
  display: flex;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  background: var(--paper-0);
  overflow-x: auto;
  scrollbar-width: none;
}
.mention-filters::-webkit-scrollbar { display: none; }

.mention-filter-chip {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: transparent;
  color: var(--ink-2);
  border: 1px solid var(--line);
  white-space: nowrap;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: background 0.12s, color 0.12s, border-color 0.12s;
}
.mention-filter-chip.active {
  background: var(--ink-0);
  color: var(--paper-0);
  border-color: var(--ink-0);
}
.mention-filter-chip:hover:not(.active) {
  background: var(--paper-2);
  border-color: var(--ink-2);
}

/* ── Body ─────────────────────────────────────────────────────── */
.mention-body {
  max-height: 360px;
  overflow-y: auto;
  padding: 6px 0;
}

.mention-group-label {
  padding: 8px 14px 4px;
  font-size: 9.5px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 600;
}

/* ── Rows ─────────────────────────────────────────────────────── */
.mention-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 14px;
  background: transparent;
  border: none;
  border-left: 2px solid transparent;
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  transition: background 0.1s;
}
.mention-row.selected {
  background: var(--ember-wash);
  border-left-color: var(--ember);
}
.mention-row:hover:not(.selected) {
  background: var(--paper-1);
}

.mention-row-icon {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border-radius: 7px;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
}

.mention-row-text {
  flex: 1;
  min-width: 0;
}
.mention-row-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-0);
  letter-spacing: -0.005em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mention-row-label.mono {
  font-family: var(--font-mono);
  letter-spacing: 0;
}
.mention-row-sub {
  font-size: 10.5px;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

.mention-row-right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.mention-child-count {
  padding: 0 4px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 3px;
  font-size: 9.5px;
  color: var(--ink-1);
  font-family: var(--font-mono);
}

.mention-tag-hint {
  font-size: 9.5px;
  color: var(--ember);
  padding: 1px 6px;
  background: var(--paper-0);
  border: 1px solid color-mix(in oklch, var(--ember) 35%, var(--line));
  border-radius: 4px;
  font-family: var(--font-mono);
}

.mention-empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 13px;
  color: var(--ink-3);
}

/* ── Footer ──────────────────────────────────────────────────── */
.mention-footer {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 14px;
  border-top: 1px solid var(--line);
  background: var(--paper-1);
  font-size: 10.5px;
  color: var(--ink-2);
}
.kbd-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.kbd {
  padding: 0 5px;
  min-width: 16px;
  text-align: center;
  background: var(--paper-0);
  border: 1px solid var(--line-2);
  border-radius: 3px;
  font-size: 10px;
  color: var(--ink-1);
  font-weight: 600;
  font-family: var(--font-mono);
  line-height: 15px;
  display: inline-block;
}
.kbd-tab-hint {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--ink-3);
}
</style>
