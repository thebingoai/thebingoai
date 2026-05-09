<template>
  <div id="user-context" class="border border-[var(--line)] rounded-[var(--r-lg)] p-6">

    <!-- Section header -->
    <div class="flex items-start justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-[var(--r-sm)] bg-[var(--ember-wash)] border border-[color-mix(in_oklch,var(--ember)_20%,var(--line))] flex items-center justify-center text-base flex-shrink-0">
          ❋
        </div>
        <div>
          <h2 class="font-serif italic text-xl font-bold text-[var(--ember)]">User context</h2>
          <p class="text-[11px] text-[var(--ink-2)] mt-0.5 leading-snug max-w-md">
            Who Bingo is talking to. Loaded into every conversation so the agent doesn't ask for the same thing twice. Distinct from Memory — these are explicit profile facts you're authoring, not things Bingo inferred.
          </p>
        </div>
      </div>
      <span class="text-[10px] font-semibold text-[var(--ink-2)] bg-[var(--paper-2)] border border-[var(--line)] px-2.5 py-1 rounded-full whitespace-nowrap">
        {{ charCount }} chars
      </span>
    </div>

    <!-- Profile fields -->
    <p class="text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-3">Profile</p>
    <div class="grid grid-cols-3 gap-5 mb-4">
      <div v-for="field in profileFields" :key="field.key">
        <label class="block text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1.5">
          {{ field.label }}
        </label>
        <input v-model="localProfile[field.key]" @input="onContextChange"
               class="w-full border-0 border-b border-[var(--line)] pb-1.5 text-[13px] text-[var(--ink-0)] bg-transparent outline-none focus:border-[var(--ember)] transition-colors" />
      </div>
    </div>

    <!-- Narrative -->
    <p class="text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-2 mt-6">
      About {{ localProfile.address_as || 'You' }} · Narrative
    </p>
    <textarea v-model="localNarrative" @input="onContextChange" rows="4"
              class="w-full border border-[var(--line)] rounded-[var(--r-sm)] px-3 py-2.5 text-xs text-[var(--ink-1)] bg-[var(--paper-0)] outline-none focus:border-[var(--ember)] resize-none transition-colors mb-2" />
    <div v-if="props.profile.published_at" class="flex justify-end mb-6">
      <span class="text-[10px] text-[var(--ink-3)]">edited recently</span>
    </div>

    <!-- Vocabulary -->
    <div class="flex items-center justify-between mb-2 mt-1">
      <p class="text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)]">
        Vocabulary · How {{ localProfile.address_as || 'You' }} Define Things
      </p>
      <button @click="addVocabTerm" class="text-[10px] font-semibold text-[var(--ember)] hover:opacity-80">
        + Add term
      </button>
    </div>
    <div class="border border-[var(--line)] rounded-[var(--r-sm)] overflow-hidden mb-6">
      <div v-for="(item, idx) in localVocab" :key="idx"
           class="flex items-center px-3 py-2 gap-3 border-b border-[var(--paper-3)] last:border-0">
        <input v-model="item.term" @input="onContextChange" placeholder="term"
               class="w-28 text-[11px] font-semibold text-[var(--ember)] font-mono bg-transparent border-none outline-none" />
        <input v-model="item.definition" @input="onContextChange" placeholder="definition"
               class="flex-1 text-[11px] text-[var(--ink-1)] bg-transparent border-none outline-none" />
        <button @click="removeVocabTerm(idx)" class="text-[11px] text-[var(--line-2)] hover:text-[var(--ink-2)]">✕</button>
      </div>
      <div v-if="localVocab.length === 0" class="px-3 py-3 text-[11px] text-[var(--ink-3)] italic">
        No terms yet. Click "+ Add term" to define vocabulary.
      </div>
    </div>

    <!-- Don't-do list -->
    <p class="text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-2">
      Sensitivities · Don't-do List
    </p>
    <div class="flex flex-wrap gap-2">
      <div v-for="(item, idx) in localSensitivities" :key="idx"
           class="flex items-center gap-1.5 text-[10px] bg-[var(--paper-0)] border border-[var(--line)] text-[var(--ink-1)] px-2.5 py-1 rounded-full">
        <span class="w-1.5 h-1.5 rounded-full bg-[oklch(0.60_0.18_25)] flex-shrink-0" />
        <span>{{ item }}</span>
        <button @click="removeSensitivity(idx)" class="text-[var(--line-2)] hover:text-[var(--ink-2)] ml-0.5">✕</button>
      </div>
      <button @click="openSensitivityModal"
              class="text-[10px] text-[var(--ink-2)] border border-dashed border-[var(--line-2)] px-3 py-1 rounded-full hover:text-[var(--ember)] hover:border-[var(--ember)] transition-colors">
        + add boundary
      </button>
    </div>

    <!-- Add sensitivity modal -->
    <div v-if="showSensitivityModal"
         class="fixed inset-0 bg-black/30 z-50 flex items-center justify-center"
         @click.self="closeSensitivityModal"
         @keydown.esc="closeSensitivityModal">
      <div class="bg-[var(--paper-0)] border border-[var(--line)] rounded-[var(--r-lg)] p-6 w-full max-w-md shadow-xl">
        <h3 class="font-serif italic text-lg font-bold text-[var(--ember)] mb-1">Add a boundary</h3>
        <p class="text-[11px] text-[var(--ink-2)] mb-4">
          Something Bingo should avoid. Example: "Don't use the word leverage".
        </p>
        <input ref="sensitivityInputRef"
               v-model="newSensitivityText"
               @keydown.enter="confirmSensitivity"
               @keydown.esc="closeSensitivityModal"
               placeholder="e.g. Avoid jargon"
               class="w-full border border-[var(--line)] rounded-[var(--r-sm)] px-3 py-2 text-xs text-[var(--ink-0)] bg-[var(--paper-0)] outline-none focus:border-[var(--ember)] transition-colors mb-4" />
        <div class="flex justify-end gap-2">
          <button @click="closeSensitivityModal"
                  class="text-[11px] font-medium border border-[var(--line)] text-[var(--ink-1)] px-3 py-1.5 rounded-[var(--r-sm)] bg-[var(--paper-0)] hover:bg-[var(--paper-2)] transition-colors">
            Cancel
          </button>
          <button @click="confirmSensitivity"
                  :disabled="!newSensitivityText.trim()"
                  class="text-[11px] font-semibold text-white bg-[var(--ember)] px-3 py-1.5 rounded-[var(--r-sm)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity">
            Add boundary
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed, nextTick, watch } from 'vue'
import type { AgentProfileData, VocabItem } from '~/composables/useAgentProfile'

const props = defineProps<{
  profile: AgentProfileData
}>()

const emit = defineEmits<{
  (e: 'update', section: string, fields: Partial<AgentProfileData>): void
}>()

const profileFields = [
  { key: 'address_as',    label: 'Address as' },
  { key: 'pronouns',      label: 'Pronouns' },
  { key: 'role',          label: 'Role' },
  { key: 'team',          label: 'Team' },
  { key: 'timezone',      label: 'Local time zone' },
  { key: 'working_hours', label: 'Working hours' },
] as const

const localProfile      = reactive({ ...(props.profile.user_profile ?? {}) })
const localNarrative    = ref(props.profile.user_narrative ?? '')
const localVocab        = reactive<VocabItem[]>([...(props.profile.vocabulary ?? [])])
const localSensitivities = reactive<string[]>([...(props.profile.sensitivities ?? [])])

// Sync local state when the parent replaces the entire profile (e.g. reset to snapshot)
watch(() => props.profile, (next) => {
  if (!next) return
  // Replace structured profile fields
  for (const k of Object.keys(localProfile)) delete (localProfile as any)[k]
  Object.assign(localProfile, next.user_profile ?? {})
  localNarrative.value = next.user_narrative ?? ''
  localVocab.splice(0, localVocab.length, ...(next.vocabulary ?? []))
  localSensitivities.splice(0, localSensitivities.length, ...(next.sensitivities ?? []))
})

const charCount = computed(() => {
  const parts = [JSON.stringify(localProfile), localNarrative.value,
                 JSON.stringify(localVocab), JSON.stringify(localSensitivities)]
  return parts.join('').length.toLocaleString()
})

function onContextChange() {
  emit('update', 'user-context', {
    user_profile:  { ...localProfile },
    user_narrative: localNarrative.value,
    vocabulary:    [...localVocab],
    sensitivities: [...localSensitivities],
  })
}

function addVocabTerm() {
  localVocab.push({ term: '', definition: '' })
  onContextChange()
}
function removeVocabTerm(idx: number) {
  localVocab.splice(idx, 1)
  onContextChange()
}

const showSensitivityModal = ref(false)
const newSensitivityText   = ref('')
const sensitivityInputRef  = ref<HTMLInputElement | null>(null)

function openSensitivityModal() {
  newSensitivityText.value = ''
  showSensitivityModal.value = true
  nextTick(() => sensitivityInputRef.value?.focus())
}

function closeSensitivityModal() {
  showSensitivityModal.value = false
  newSensitivityText.value = ''
}

function confirmSensitivity() {
  const text = newSensitivityText.value.trim()
  if (!text) return
  localSensitivities.push(text)
  onContextChange()
  closeSensitivityModal()
}
function removeSensitivity(idx: number) {
  localSensitivities.splice(idx, 1)
  onContextChange()
}
</script>
