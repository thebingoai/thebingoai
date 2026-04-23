<template>
  <div class="rounded-xl border border-gray-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg overflow-hidden">
    <!-- Search input -->
    <div class="px-3 py-2 border-b border-gray-100 dark:border-neutral-700 flex items-center gap-2">
      <!-- Back button (items level) -->
      <button
        v-if="props.mentionLevel === 'items'"
        type="button"
        class="text-gray-400 dark:text-neutral-500 hover:text-gray-600 dark:hover:text-neutral-300 transition-colors shrink-0"
        @mousedown.prevent
        @click="handleBack"
      >
        <ChevronLeft class="h-4 w-4" />
      </button>
      <Search class="h-4 w-4 text-gray-400 dark:text-neutral-500 shrink-0" />
      <input
        ref="searchRef"
        :value="mentionQuery"
        @input="setQuery(($event.target as HTMLInputElement).value)"
        @keydown="handleKeydown"
        :placeholder="props.mentionLevel === 'root' ? 'Search connections, pages…' : `Search in ${props.activeGroup?.label ?? ''}…`"
        class="flex-1 text-sm bg-transparent outline-none text-gray-700 dark:text-neutral-200 placeholder-gray-400 dark:placeholder-neutral-500 min-w-0"
        autocomplete="off"
      />
      <button
        type="button"
        class="text-gray-400 dark:text-neutral-500 hover:text-gray-600 dark:hover:text-neutral-300 transition-colors"
        @mousedown.prevent="emit('close')"
      >
        <X class="h-4 w-4" />
      </button>
    </div>

    <!-- Active group breadcrumb -->
    <div v-if="props.mentionLevel === 'items' && props.activeGroup" class="px-3 py-1.5 bg-gray-50 dark:bg-neutral-700/50 border-b border-gray-100 dark:border-neutral-700 flex items-center gap-1.5">
      <component :is="groupIcon(props.activeGroup.iconType)" class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-500 shrink-0" />
      <span class="text-xs font-medium text-gray-600 dark:text-neutral-300">{{ props.activeGroup.label }}</span>
      <span class="text-xs text-gray-400 dark:text-neutral-500 ml-auto">{{ props.activeGroupItems.length }} item{{ props.activeGroupItems.length !== 1 ? 's' : '' }}</span>
    </div>

    <!-- Results -->
    <div class="max-h-64 overflow-y-auto">

      <!-- ROOT LEVEL: group list -->
      <template v-if="props.mentionLevel === 'root'">
        <button
          v-for="(group, i) in props.filteredGroups"
          :key="group.id"
          type="button"
          class="w-full flex items-center gap-3 px-3 py-2.5 text-sm text-left transition-colors"
          :class="i === activeIndex
            ? 'bg-gray-100 dark:bg-neutral-700 text-gray-900 dark:text-white'
            : 'text-gray-700 dark:text-neutral-200 hover:bg-gray-50 dark:hover:bg-neutral-700/50'"
          @mousedown.prevent
          @click="selectGroup(group)"
        >
          <div class="h-7 w-7 rounded-md flex items-center justify-center shrink-0"
            :class="{
              'bg-purple-100 dark:bg-purple-900/30': group.iconType === 'dashboard',
              'bg-blue-100 dark:bg-blue-900/30': group.iconType === 'database',
              'bg-gray-100 dark:bg-neutral-700': group.iconType === 'notion',
            }"
          >
            <component :is="groupIcon(group.iconType)"
              class="h-4 w-4"
              :class="{
                'text-purple-600 dark:text-purple-400': group.iconType === 'dashboard',
                'text-blue-600 dark:text-blue-400': group.iconType === 'database',
                'text-gray-600 dark:text-neutral-400': group.iconType === 'notion',
              }"
            />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-900 dark:text-neutral-100 truncate">{{ group.label }}</p>
            <p class="text-xs text-gray-400 dark:text-neutral-500">{{ group.subLabel }}</p>
          </div>
          <ChevronRight class="h-4 w-4 text-gray-300 dark:text-neutral-600 shrink-0" />
        </button>

        <div v-if="props.filteredGroups.length === 0" class="px-3 py-5 text-sm text-gray-400 dark:text-neutral-500 text-center">
          No matches
        </div>
      </template>

      <!-- ITEMS LEVEL: item list -->
      <template v-else-if="props.mentionLevel === 'items'">
        <template v-if="props.activeGroupItems.length > 0">
          <button
            v-for="(item, i) in props.activeGroupItems"
            :key="`item-${item.type}-${item.id}-${item.pageId ?? ''}`"
            type="button"
            class="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-left transition-colors"
            :class="i === activeIndex
              ? 'bg-gray-100 dark:bg-neutral-700 text-gray-900 dark:text-white'
              : 'text-gray-700 dark:text-neutral-200 hover:bg-gray-50 dark:hover:bg-neutral-700/50'"
            @mousedown.prevent="emit('select', item)"
          >
            <component :is="itemIcon(item)" class="h-4 w-4 text-gray-400 dark:text-neutral-500 shrink-0" />
            <span class="truncate">{{ item.displayName }}</span>
            <span v-if="item.dbType" class="ml-auto text-xs text-gray-400 dark:text-neutral-500 shrink-0">{{ item.dbType }}</span>
          </button>
        </template>

        <div v-else class="px-3 py-4 text-sm text-gray-400 dark:text-neutral-500 text-center">
          <template v-if="props.activeGroup?.count === 0 && props.activeGroup?.iconType === 'notion'">
            No pages synced — share pages with your Notion integration, then Sync Now.
          </template>
          <template v-else>
            No matches
          </template>
        </div>
      </template>

    </div>
  </div>
</template>

<script setup lang="ts">
import { Search, X, ChevronRight, ChevronLeft, LayoutDashboard, Database, FileText } from 'lucide-vue-next'
import type { MentionItem, MentionGroup } from '~/composables/useMentions'

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
const { mentionQuery, setQuery, drillIntoGroup, goBackToRoot } = useMentions()

const activeIndex = ref(0)

const listLength = computed(() =>
  props.mentionLevel === 'root'
    ? props.filteredGroups.length
    : props.activeGroupItems.length
)

watch(() => [props.filteredGroups, props.activeGroupItems, props.mentionLevel], () => {
  activeIndex.value = 0
})

onMounted(() => nextTick(() => searchRef.value?.focus()))

function groupIcon(type: MentionGroup['iconType']) {
  if (type === 'dashboard') return LayoutDashboard
  if (type === 'database') return Database
  return FileText
}

function itemIcon(item: MentionItem) {
  if (item.type === 'dashboard') return LayoutDashboard
  if (item.type === 'notion_page') return FileText
  return Database
}

function selectGroup(group: MentionGroup) {
  drillIntoGroup(group.id)
}

function handleBack() {
  goBackToRoot()
  emit('back')
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, listLength.value - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(0, activeIndex.value - 1)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (props.mentionLevel === 'root') {
      const group = props.filteredGroups[activeIndex.value]
      if (group) selectGroup(group)
    } else {
      const item = props.activeGroupItems[activeIndex.value]
      if (item) emit('select', item)
    }
  } else if (e.key === 'Escape') {
    e.preventDefault()
    if (props.mentionLevel === 'items') {
      handleBack()
    } else {
      emit('close')
    }
  } else if (e.key === 'Backspace' && !mentionQuery.value && props.mentionLevel === 'items') {
    handleBack()
  }
}
</script>
