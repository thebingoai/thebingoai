<template>
  <!-- GridStack container -->
  <div ref="containerRef" class="grid-stack w-full" :class="editMode ? 'edit-mode' : ''">
    <!-- GridStack items are created imperatively by the composable -->
  </div>

  <!-- Teleport widget content into each GridStack item's content div -->
  <template v-for="widget in widgets" :key="widget.id">
    <Teleport
      v-if="contentRefs.has(widget.id)"
      :to="contentRefs.get(widget.id)!"
    >
      <DashboardWidget
        :widget="widget"
        :edit-mode="editMode"
        @remove="onRemove"
        @open-sql-editor="(id, err) => emit('open-sql-editor', id, err)"
        @edit-config="emit('edit-config', $event)"
      />
    </Teleport>
  </template>
</template>

<script setup lang="ts">
import type { DashboardWidget } from '~/types/dashboard'
import { useDashboardGrid } from '~/composables/useDashboardGrid'
import { useDashboardStore } from '~/stores/dashboard'

const props = defineProps<{
  widgets: DashboardWidget[]
  editMode: boolean
}>()

const emit = defineEmits<{
  'open-sql-editor': [id: string, error?: string]
  'edit-config': [id: string]
}>()

const store = useDashboardStore()
const containerRef = ref<HTMLElement | null>(null)
const widgetsRef = computed(() => props.widgets)

const { contentRefs } = useDashboardGrid(containerRef, widgetsRef)

function onRemove(id: string) {
  store.removeWidget(id)
}
</script>
