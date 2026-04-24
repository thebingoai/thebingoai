<template>
  <!-- Header -->
  <div class="flex items-center gap-2 shrink-0">
    <h3 class="text-sm font-medium text-gray-900 dark:text-neutral-100">Database Schema</h3>
    <span v-if="schema" class="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded-full dark:bg-neutral-700 dark:text-neutral-400">
      {{ schema.table_names.length }} tables
    </span>
  </div>

  <!-- Loading state -->
  <div v-if="loading" class="space-y-2 shrink-0">
    <UiSkeleton class="h-5 w-full" />
    <UiSkeleton class="h-5 w-5/6" />
    <UiSkeleton class="h-5 w-4/6" />
  </div>

  <!-- Error state -->
  <div v-else-if="error" class="text-sm text-red-500 shrink-0">
    {{ error }}
  </div>

  <!-- No schema yet -->
  <div v-else-if="!schema" class="flex items-center gap-2 text-sm text-gray-400 dark:text-neutral-400 shrink-0">
    <Database class="h-4 w-4" />
    Click "Refresh Schema" to discover database structure.
  </div>

  <!-- Empty state (schema loaded but no tables). Slot lets caller add context (e.g. BigQuery permission hint). -->
  <div v-else-if="!schema.table_names?.length" class="shrink-0">
    <slot name="empty">
      <div class="flex items-center gap-2 text-sm text-gray-400 dark:text-neutral-400">
        <Database class="h-4 w-4" />
        No tables found.
      </div>
    </slot>
  </div>

  <!-- Schema tree -->
  <template v-else>
    <!-- Search -->
    <div class="relative shrink-0">
      <Search class="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-gray-400" />
      <input
        v-model="schemaSearch"
        type="text"
        placeholder="Filter tables..."
        class="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
    </div>

    <!-- Tree -->
    <div class="overflow-y-auto flex-1 space-y-1">
      <div v-for="(schemaData, schemaName) in filteredSchemas" :key="schemaName">
        <!-- Schema row -->
        <button
          @click="toggleSchema(String(schemaName))"
          class="flex items-center gap-1.5 w-full text-left py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-neutral-700"
        >
          <component :is="expandedSchemas[String(schemaName)] ? ChevronDown : ChevronRight" class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-400 shrink-0" />
          <Database class="h-3.5 w-3.5 text-gray-500 dark:text-neutral-400 shrink-0" />
          <span class="text-xs font-medium text-gray-700 dark:text-neutral-200 truncate">{{ schemaName }}</span>
          <span class="text-xs text-gray-400 dark:text-neutral-500 ml-auto shrink-0">{{ Object.keys(schemaData.tables).length }}</span>
        </button>

        <!-- Tables -->
        <div v-if="expandedSchemas[String(schemaName)]" class="ml-4 space-y-0.5">
          <div v-for="(tableData, tableName) in schemaData.tables" :key="tableName">
            <!-- Table row -->
            <button
              @click="toggleTable(`${schemaName}.${tableName}`)"
              class="flex items-center gap-1.5 w-full text-left py-1 px-2 rounded hover:bg-gray-50 dark:hover:bg-neutral-700"
            >
              <component :is="expandedTables[`${schemaName}.${tableName}`] ? ChevronDown : ChevronRight" class="h-3.5 w-3.5 text-gray-400 dark:text-neutral-400 shrink-0" />
              <Table2 class="h-3.5 w-3.5 text-blue-500 shrink-0" />
              <span class="text-xs text-gray-700 dark:text-neutral-200 truncate">{{ tableName }}</span>
              <span v-if="tableData.row_count != null" class="text-xs text-gray-400 dark:text-neutral-500 ml-auto shrink-0">{{ tableData.row_count.toLocaleString() }}</span>
            </button>

            <!-- Columns -->
            <div v-if="expandedTables[`${schemaName}.${tableName}`]" class="ml-6 space-y-0.5">
              <div
                v-for="col in tableData.columns"
                :key="col.name"
                class="flex items-center gap-1.5 py-0.5 px-2 text-xs"
              >
                <Key v-if="col.primary_key" class="h-3 w-3 text-amber-500 shrink-0" />
                <span v-else class="h-3 w-3 shrink-0" />
                <span class="text-gray-600 dark:text-neutral-300 truncate">{{ col.name }}</span>
                <span class="text-gray-600 dark:text-neutral-200 bg-gray-100 dark:bg-neutral-700 px-1 py-0.5 rounded font-mono ml-auto shrink-0 text-xs">{{ col.type }}</span>
                <span v-if="col.nullable" class="text-gray-400 dark:text-neutral-500 shrink-0">?</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Relationships -->
      <div v-if="schema.relationships.length > 0" class="border-t border-gray-100 pt-3 mt-2">
        <h4 class="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">Relationships</h4>
        <div class="space-y-1">
          <div
            v-for="rel in schema.relationships"
            :key="`${rel.from}-${rel.to}`"
            class="flex items-center gap-1.5 text-xs text-gray-500"
          >
            <Link2 class="h-3 w-3 shrink-0" />
            <span class="font-mono truncate">{{ rel.from }}</span>
            <span class="shrink-0">→</span>
            <span class="font-mono truncate">{{ rel.to }}</span>
          </div>
        </div>
      </div>
    </div>
  </template>
</template>

<script setup lang="ts">
import { ChevronDown, ChevronRight, Database, Key, Link2, Search, Table2 } from 'lucide-vue-next'
import type { DatabaseSchema } from '~/types/connection'

const props = defineProps<{
  schema: DatabaseSchema | null
  loading: boolean
  error: string | null
}>()

const schemaSearch = ref('')
const expandedSchemas = ref<Record<string, boolean>>({})
const expandedTables = ref<Record<string, boolean>>({})

function toggleSchema(name: string) {
  expandedSchemas.value[name] = !expandedSchemas.value[name]
}

function toggleTable(key: string) {
  expandedTables.value[key] = !expandedTables.value[key]
}

// Auto-expand the first schema each time a new schema loads (preserves the
// previous UX where community auto-expanded the first schema on refresh).
watch(() => props.schema, (s) => {
  if (!s) {
    expandedSchemas.value = {}
    expandedTables.value = {}
    schemaSearch.value = ''
    return
  }
  const names = Object.keys(s.schemas)
  if (names.length > 0 && !expandedSchemas.value[names[0]]) {
    expandedSchemas.value = { [names[0]]: true }
  }
})

const filteredSchemas = computed(() => {
  if (!props.schema) return {}
  const search = schemaSearch.value.toLowerCase()
  if (!search) return props.schema.schemas
  const result: Record<string, any> = {}
  for (const [schemaName, schemaData] of Object.entries(props.schema.schemas)) {
    const filteredTables: Record<string, any> = {}
    for (const [tableName, tableData] of Object.entries((schemaData as any).tables)) {
      if (tableName.toLowerCase().includes(search)) {
        filteredTables[tableName] = tableData
      }
    }
    if (Object.keys(filteredTables).length > 0) {
      result[schemaName] = { ...(schemaData as any), tables: filteredTables }
    }
  }
  return result
})
</script>
