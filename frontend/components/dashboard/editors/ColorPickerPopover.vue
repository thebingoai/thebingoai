<template>
  <div class="relative inline-block" ref="rootRef">
    <button
      type="button"
      :disabled="disabled"
      class="h-6 w-10 rounded border border-gray-200 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 overflow-hidden"
      :style="swatchStyle"
      @click="open = !open"
    >
      <span v-if="!modelValue" class="block h-full w-full"
        style="background:
          linear-gradient(45deg, #ddd 25%, transparent 25%),
          linear-gradient(-45deg, #ddd 25%, transparent 25%),
          linear-gradient(45deg, transparent 75%, #ddd 75%),
          linear-gradient(-45deg, transparent 75%, #ddd 75%);
          background-size: 8px 8px;
          background-position: 0 0, 0 4px, 4px -4px, -4px 0px;"
      />
    </button>

    <div
      v-if="open"
      class="absolute right-0 top-7 z-50 w-64 rounded-lg border border-gray-200 bg-white p-3 shadow-xl"
    >
      <!-- Header: Reset / Transparent -->
      <div class="flex items-center justify-between pb-2 border-b border-gray-100">
        <button
          type="button"
          class="flex items-center gap-1 text-[11px] text-gray-600 hover:text-indigo-600"
          @click="select(undefined)"
        >
          <RotateCcw class="h-3 w-3" /> Reset
        </button>
        <button
          type="button"
          class="flex items-center gap-1 text-[11px] text-gray-600 hover:text-indigo-600"
          @click="select('transparent')"
        >
          <Ban class="h-3 w-3" /> Transparent
        </button>
      </div>

      <!-- Preset palette -->
      <div class="mt-3 space-y-1.5">
        <div v-for="(row, ri) in PRESET_ROWS" :key="ri" class="flex gap-1">
          <button
            v-for="color in row"
            :key="color"
            type="button"
            class="h-5 w-5 rounded-full border border-black/10 hover:scale-110 transition-transform"
            :style="{ background: color }"
            :title="color"
            @click="select(color)"
          />
        </div>
      </div>

      <!-- Custom color -->
      <div class="mt-3 pt-2 border-t border-gray-100 flex items-center justify-between gap-2">
        <span class="text-[11px] text-gray-500 uppercase tracking-wide">Custom</span>
        <input
          type="color"
          :value="modelValue && modelValue !== 'transparent' ? modelValue : '#6366f1'"
          class="h-6 w-10 rounded border border-gray-200 cursor-pointer p-0.5"
          @input="select(($event.target as HTMLInputElement).value)"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { RotateCcw, Ban } from 'lucide-vue-next'

const props = defineProps<{
  modelValue: string | undefined
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string | undefined]
}>()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const PRESET_ROWS: string[][] = [
  ['#000000', '#1f2937', '#374151', '#4b5563', '#6b7280', '#9ca3af', '#d1d5db', '#f3f4f6', '#ffffff'],
  ['#dc2626', '#ea580c', '#d97706', '#65a30d', '#16a34a', '#0891b2', '#2563eb', '#7c3aed', '#c026d3'],
  ['#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#d946ef'],
  ['#f87171', '#fb923c', '#fbbf24', '#a3e635', '#4ade80', '#22d3ee', '#60a5fa', '#a78bfa', '#e879f9'],
  ['#fecaca', '#fed7aa', '#fde68a', '#d9f99d', '#bbf7d0', '#a5f3fc', '#bfdbfe', '#ddd6fe', '#f5d0fe'],
]

const swatchStyle = computed(() => {
  if (!props.modelValue) return { background: 'transparent' }
  return { background: props.modelValue }
})

function select(color: string | undefined) {
  emit('update:modelValue', color)
  open.value = false
}

function onClickOutside(e: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(e.target as Node)) {
    open.value = false
  }
}

onMounted(() => {
  window.addEventListener('mousedown', onClickOutside)
})

onBeforeUnmount(() => {
  window.removeEventListener('mousedown', onClickOutside)
})
</script>
