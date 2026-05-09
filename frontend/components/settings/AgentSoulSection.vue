<template>
  <div id="soul" class="border border-[var(--line)] rounded-[var(--r-lg)] p-6">

    <!-- Section header -->
    <div class="flex items-start justify-between mb-5">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-[var(--r-sm)] bg-[var(--ember-wash)] border border-[color-mix(in_oklch,var(--ember)_20%,var(--line))] flex items-center justify-center text-base flex-shrink-0">
          ✦
        </div>
        <div>
          <h2 class="font-serif italic text-xl font-bold text-[var(--ember)]">Soul</h2>
          <p class="text-[11px] text-[var(--ink-2)] mt-0.5 leading-snug max-w-md">
            The operating principles Bingo holds across every session. Read at the start of every conversation. Keep it short — every line is paid for in tokens and attention.
          </p>
        </div>
      </div>
      <span class="text-[10px] font-semibold text-[var(--ink-2)] bg-[var(--paper-2)] border border-[var(--line)] px-2.5 py-1 rounded-full whitespace-nowrap">
        {{ tokenEstimate }} tokens
      </span>
    </div>

    <!-- Editor -->
    <div class="border border-[var(--line)] rounded-[var(--r-md)] overflow-hidden mb-4">

      <!-- Tab bar -->
      <div class="flex items-center justify-between px-3 py-1.5 bg-[var(--paper-1)] border-b border-[var(--line)]">
        <div class="flex gap-1">
          <span class="text-[10px] px-2 py-1 rounded-[var(--r-sm)] bg-[var(--paper-0)] border border-[var(--line)] text-[var(--ink-0)] font-medium font-mono">
            soul.md
          </span>
          <span class="text-[10px] px-2 py-1 text-[var(--ink-2)] font-mono">markdown</span>
        </div>
      </div>

      <!-- Text area -->
      <textarea
        v-model="localSoul"
        @input="onSoulChange"
        rows="16"
        spellcheck="false"
        class="w-full p-4 font-mono text-xs leading-relaxed text-[var(--ink-1)] bg-[var(--paper-0)] resize-none outline-none border-none"
        placeholder="# Operating principles&#10;&#10;You are Bingo..."
      />

      <!-- Footer -->
      <div class="flex items-center justify-between px-3 py-1.5 bg-[var(--paper-1)] border-t border-[var(--line)]">
        <span class="text-[10px] text-[var(--ink-3)] font-mono">
          {{ lineCount }} lines · {{ tokenEstimate }} tokens
        </span>
        <span class="text-[10px] font-medium flex items-center gap-1.5"
              :class="saving ? 'text-[var(--ink-3)]' : 'text-[var(--ok)]'">
          <span class="w-1.5 h-1.5 rounded-full inline-block"
                :class="saving ? 'bg-[var(--ink-3)]' : 'bg-[var(--ok)]'" />
          {{ saving ? 'saving…' : 'saved' }}
        </span>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { AgentProfileData } from '~/composables/useAgentProfile'

const props = defineProps<{
  profile: AgentProfileData
  saving: boolean
}>()

const emit = defineEmits<{
  (e: 'update', section: string, fields: Partial<AgentProfileData>): void
}>()

const localSoul = ref(props.profile.soul ?? '')

// Sync local state when the parent replaces the entire profile (e.g. reset to snapshot)
watch(() => props.profile, (next) => {
  if (!next) return
  localSoul.value = next.soul ?? ''
})

const lineCount = computed(() => localSoul.value.split('\n').length)
// Rough token estimate: ~4 chars per token
const tokenEstimate = computed(() => Math.ceil(localSoul.value.length / 4).toLocaleString())

function onSoulChange() {
  emit('update', 'soul', { soul: localSoul.value })
}
</script>
