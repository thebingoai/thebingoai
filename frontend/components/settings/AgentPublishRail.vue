<template>
  <div class="w-48 flex-shrink-0 border-r border-[var(--line)] flex flex-col px-3 py-5">

    <p class="text-[9px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-3">
      Sections
    </p>

    <!-- Section links -->
    <nav class="flex-1 space-y-0.5">
      <a
        v-for="section in sections"
        :key="section.id"
        :href="`#${section.id}`"
        class="flex items-center gap-2.5 px-2.5 py-2 rounded-[var(--r-md)] cursor-pointer no-underline transition-colors"
        :class="activeSection === section.id
          ? 'bg-[var(--ember-wash)]'
          : 'hover:bg-[var(--ember-wash)]'"
        @click.prevent="onNavigate(section.id)"
      >
        <div
          class="w-7 h-7 rounded-[var(--r-sm)] flex items-center justify-center text-sm flex-shrink-0 transition-[background-color,color] border"
          :class="activeSection === section.id
            ? 'bg-[var(--ember-wash)] text-[var(--ember)] border-[color-mix(in_oklch,var(--ember)_25%,var(--line))]'
            : 'bg-[var(--paper-2)] text-[var(--ink-2)] border-transparent'"
        >
          {{ section.icon }}
        </div>
        <div>
          <p
            class="text-xs font-semibold"
            :class="activeSection === section.id ? 'text-[var(--ember)]' : 'text-[var(--ink-1)]'"
          >
            {{ section.label }}
          </p>
          <p class="text-[10px] text-[var(--ink-3)] leading-tight mt-0.5">
            {{ section.subtitle }}
          </p>
        </div>
      </a>
    </nav>

    <!-- Publish footer -->
    <div class="mt-4 pt-4 border-t border-dashed border-[var(--line-2)]">
      <p class="text-[10px] text-[var(--ink-3)] leading-snug mb-3">
        Edits save as a <strong class="text-[var(--ink-2)] font-semibold">{{ versionLabel }} draft</strong>.
        Publish to make Bingo follow them in new threads.
      </p>
      <button
        class="w-full py-1.5 text-[11px] font-bold rounded-[var(--r-sm)] bg-[var(--ember)] text-white hover:opacity-90 transition-opacity disabled:opacity-50"
        :disabled="publishing"
        @click="$emit('publish')"
      >
        {{ publishing ? 'Publishing…' : '✓ Publish' }}
      </button>
      <button
        v-if="canReset"
        class="w-full mt-2 py-1.5 text-[11px] font-medium rounded-[var(--r-sm)] border border-[var(--line-2)] bg-[var(--paper-0)] text-[var(--ink-2)] hover:text-[var(--ink-0)] hover:bg-[var(--paper-2)] transition-colors disabled:opacity-50"
        :disabled="resetting"
        @click="$emit('reset')"
      >
        {{ resetting ? 'Reverting…' : '↺ Reset draft' }}
      </button>
      <button
        class="w-full mt-2 py-1.5 text-[11px] font-medium rounded-[var(--r-sm)] border border-[var(--line-2)] bg-[var(--paper-0)] text-[var(--ink-3)] hover:text-[var(--ink-0)] hover:bg-[var(--paper-2)] transition-colors disabled:opacity-50"
        :disabled="resetting"
        @click="$emit('factory-reset')"
      >
        ⟲ Revert to Bingo default
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  activeSection: string
  versionLabel: string
  publishing: boolean
  resetting: boolean
  canReset: boolean
  scrollContainer: HTMLElement | null
}>()

const emit = defineEmits<{
  (e: 'publish'): void
  (e: 'reset'): void
  (e: 'factory-reset'): void
  (e: 'navigate', id: string): void
}>()

const sections = [
  { id: 'identity',     icon: '⚡', label: 'Identity',     subtitle: 'Name, voice, model defaults' },
  { id: 'soul',         icon: '✦', label: 'Soul',         subtitle: 'Operating principles · system prompt' },
  { id: 'user-context', icon: '❋', label: 'User context', subtitle: 'Who Bingo is talking to' },
]

function onNavigate(id: string) {
  emit('navigate', id)
  const container = props.scrollContainer
  const target = document.getElementById(id)
  if (!container || !target) return
  container.scrollTo({ top: target.offsetTop - 16, behavior: 'smooth' })
}
</script>
