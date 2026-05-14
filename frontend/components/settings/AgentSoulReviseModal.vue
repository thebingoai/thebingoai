<template>
  <div class="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4"
       @click.self="$emit('close')"
       @keydown.esc="$emit('close')">
    <div class="bg-[var(--paper-0)] border border-[var(--line)] rounded-[var(--r-lg)] w-full max-w-2xl shadow-xl flex flex-col overflow-hidden"
         style="max-height: 80vh;">

      <!-- Header -->
      <div class="px-5 py-4 border-b border-[var(--line)] flex-shrink-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="text-base">✦</span>
          <h3 class="font-serif italic text-lg font-bold text-[var(--ember)]">Suggested revision</h3>
        </div>
        <p class="text-[11px] text-[var(--ink-2)] leading-relaxed">
          Bingo cleaned up your soul prompt — review before accepting. Accepting will replace your current draft.
        </p>
      </div>

      <!-- Suggestion content -->
      <div class="flex-1 overflow-y-auto p-5">
        <pre class="font-mono text-[11px] leading-relaxed text-[var(--ink-1)] whitespace-pre-wrap bg-[var(--paper-1)] border border-[var(--line)] rounded-[var(--r-md)] p-4">{{ suggestion }}</pre>
      </div>

      <!-- Footer -->
      <div class="flex justify-end gap-2 px-5 py-3.5 border-t border-[var(--line)] flex-shrink-0">
        <button @click="$emit('discard')"
                class="text-[11px] font-medium border border-[var(--line)] text-[var(--ink-1)] px-3 py-1.5 rounded-[var(--r-sm)] bg-[var(--paper-0)] hover:bg-[var(--paper-2)] transition-colors">
          Discard
        </button>
        <button @click="$emit('accept', suggestion)"
                class="text-[11px] font-semibold text-white bg-[var(--ember)] px-3 py-1.5 rounded-[var(--r-sm)] hover:opacity-90 transition-opacity">
          Accept revision
        </button>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  suggestion: string
  original: string
}>()

defineEmits<{
  (e: 'accept', suggestion: string): void
  (e: 'discard'): void
  (e: 'close'): void
}>()
</script>
