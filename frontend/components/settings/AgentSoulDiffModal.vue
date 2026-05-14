<template>
  <div class="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
       @click.self="$emit('close')"
       @keydown.esc="$emit('close')">
    <div class="bg-[var(--paper-0)] border border-[var(--line)] rounded-[var(--r-lg)] w-full max-w-4xl shadow-xl flex flex-col overflow-hidden"
         style="max-height: 80vh;">

      <!-- Header -->
      <div class="flex items-center justify-between px-5 py-3.5 border-b border-[var(--line)] flex-shrink-0">
        <div>
          <h3 class="font-serif italic text-lg font-bold text-[var(--ember)]">Diff vs published</h3>
          <p class="text-[10px] text-[var(--ink-3)] mt-0.5">Lines that changed since the last publish.</p>
        </div>
        <button @click="$emit('close')"
                class="text-[var(--ink-2)] hover:text-[var(--ink-0)] text-lg leading-none px-2">✕</button>
      </div>

      <!-- Column labels -->
      <div class="grid grid-cols-2 border-b border-[var(--line)] flex-shrink-0">
        <div class="px-4 py-2 bg-[oklch(0.97_0.02_25)] border-r border-[var(--line)]">
          <span class="text-[9px] font-bold uppercase tracking-[.08em] text-[oklch(0.55_0.15_25)]">Published</span>
        </div>
        <div class="px-4 py-2 bg-[oklch(0.97_0.04_150)]">
          <span class="text-[9px] font-bold uppercase tracking-[.08em] text-[oklch(0.45_0.15_150)]">Current draft</span>
        </div>
      </div>

      <!-- Diff rows -->
      <div class="overflow-y-auto flex-1 font-mono text-[11px] leading-relaxed">
        <div v-for="(row, idx) in diffRows" :key="idx"
             class="grid grid-cols-2 border-b border-[var(--paper-3)] last:border-0"
             :class="row.changed ? 'bg-[var(--paper-1)]' : ''">
          <!-- Published side -->
          <div class="px-4 py-1 border-r border-[var(--line)]"
               :class="row.changed && row.published !== '' ? 'bg-[oklch(0.96_0.03_25)]' : ''">
            <span :class="row.changed && row.published !== '' ? 'text-[oklch(0.45_0.18_25)]' : 'text-[var(--ink-2)]'">
              {{ row.published || '&nbsp;' }}
            </span>
          </div>
          <!-- Current side -->
          <div class="px-4 py-1"
               :class="row.changed && row.current !== '' ? 'bg-[oklch(0.96_0.05_150)]' : ''">
            <span :class="row.changed && row.current !== '' ? 'text-[oklch(0.35_0.18_150)]' : 'text-[var(--ink-1)]'">
              {{ row.current || '&nbsp;' }}
            </span>
          </div>
        </div>
        <div v-if="diffRows.length === 0"
             class="flex items-center justify-center py-12 text-sm text-[var(--ink-3)]">
          No differences found.
        </div>
      </div>

      <!-- Footer -->
      <div class="flex justify-end px-5 py-3.5 border-t border-[var(--line)] flex-shrink-0">
        <button @click="$emit('close')"
                class="text-[11px] font-medium border border-[var(--line)] text-[var(--ink-1)] px-3 py-1.5 rounded-[var(--r-sm)] bg-[var(--paper-0)] hover:bg-[var(--paper-2)] transition-colors">
          Close
        </button>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  published: string
  current: string
}>()

defineEmits<{ (e: 'close'): void }>()

const diffRows = computed(() => {
  const pubLines = props.published.split('\n')
  const curLines = props.current.split('\n')
  const len = Math.max(pubLines.length, curLines.length)
  const rows: { published: string; current: string; changed: boolean }[] = []
  for (let i = 0; i < len; i++) {
    const p = pubLines[i] ?? ''
    const c = curLines[i] ?? ''
    rows.push({ published: p, current: c, changed: p !== c })
  }
  return rows
})
</script>
