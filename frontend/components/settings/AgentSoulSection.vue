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
        <div class="flex gap-1 items-center">
          <span class="text-[10px] px-2 py-1 rounded-[var(--r-sm)] bg-[var(--paper-0)] border border-[var(--line)] text-[var(--ink-0)] font-medium font-mono">
            soul.md
          </span>
          <span class="text-[10px] px-2 py-1 text-[var(--ink-2)] font-mono">markdown</span>
        </div>
        <!-- Toolbar actions -->
        <div class="flex items-center gap-1">
          <button @click="showDiff = true"
                  :disabled="!hasPublishedDiff"
                  class="text-[10px] px-2 py-1 rounded-[var(--r-sm)] text-[var(--ink-2)] hover:bg-[var(--paper-2)] disabled:opacity-30 disabled:cursor-not-allowed transition-colors">
            ⇄ Diff vs published
          </button>
          <button @click="onRevise"
                  :disabled="revising"
                  class="text-[10px] px-2 py-1 rounded-[var(--r-sm)] text-[var(--ember)] hover:bg-[var(--ember-wash)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium">
            ✦ {{ revising ? 'Asking…' : 'Ask Bingo to revise' }}
          </button>
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
          {{ lineCount }} lines · {{ tokenEstimate }} tokens · ~${{ costEstimate }} / call
        </span>
        <span class="text-[10px] font-medium flex items-center gap-1.5"
              :class="saving ? 'text-[var(--ink-3)]' : 'text-[var(--ok)]'">
          <span class="w-1.5 h-1.5 rounded-full inline-block"
                :class="saving ? 'bg-[var(--ink-3)]' : 'bg-[var(--ok)]'" />
          {{ saving ? 'saving…' : savedLabel }}
        </span>
      </div>
    </div>

    <!-- Style references -->
    <div class="mt-2">
      <div class="flex items-center justify-between mb-2">
        <p class="text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)]">Style References</p>
        <button v-if="!addingRef" @click="startAddRef"
                class="text-[10px] font-semibold text-[var(--ember)] hover:opacity-80">
          + Add reference
        </button>
      </div>

      <!-- Existing refs as chips -->
      <div class="flex flex-wrap gap-2 mb-2">
        <div v-for="(ref, idx) in localRefs" :key="idx"
             class="inline-flex items-center gap-1.5 text-[10px] bg-[var(--paper-1)] border border-[var(--line)] text-[var(--ink-1)] px-2.5 py-1 rounded-[var(--r-sm)]">
          <span class="text-[11px]">{{ ref.type === 'doc' ? '📄' : '🔗' }}</span>
          <span>{{ ref.title }}</span>
          <button @click="removeRef(idx)" class="text-[var(--line-2)] hover:text-[var(--ink-2)] ml-0.5">✕</button>
        </div>
        <div v-if="localRefs.length === 0 && !addingRef"
             class="text-[10px] text-[var(--ink-3)] italic">
          No references attached.
        </div>
      </div>

      <!-- Inline add form -->
      <div v-if="addingRef"
           class="border border-[var(--line)] rounded-[var(--r-md)] p-3 bg-[var(--paper-1)]">
        <div class="grid grid-cols-[80px_1fr_1fr] gap-2 items-end mb-2">
          <div>
            <label class="block text-[9px] font-bold uppercase tracking-[.08em] text-[var(--ink-3)] mb-1">Type</label>
            <select v-model="newRefType"
                    class="w-full text-[11px] border border-[var(--line)] rounded-[var(--r-sm)] px-2 py-1 bg-[var(--paper-0)] outline-none focus:border-[var(--ember)] text-[var(--ink-0)]">
              <option value="link">Link</option>
              <option value="doc">Doc</option>
            </select>
          </div>
          <div>
            <label class="block text-[9px] font-bold uppercase tracking-[.08em] text-[var(--ink-3)] mb-1">Title</label>
            <input v-model="newRefTitle" ref="refTitleInputRef"
                   placeholder="e.g. Economist house style"
                   class="w-full text-[11px] border border-[var(--line)] rounded-[var(--r-sm)] px-2 py-1 bg-[var(--paper-0)] outline-none focus:border-[var(--ember)] text-[var(--ink-0)]" />
          </div>
          <div>
            <label class="block text-[9px] font-bold uppercase tracking-[.08em] text-[var(--ink-3)] mb-1">URL / ID</label>
            <input v-model="newRefPointer"
                   placeholder="https://..."
                   class="w-full text-[11px] border border-[var(--line)] rounded-[var(--r-sm)] px-2 py-1 bg-[var(--paper-0)] outline-none focus:border-[var(--ember)] text-[var(--ink-0)]" />
          </div>
        </div>
        <div class="flex justify-end gap-2">
          <button @click="cancelAddRef"
                  class="text-[10px] font-medium border border-[var(--line)] text-[var(--ink-1)] px-2.5 py-1 rounded-[var(--r-sm)] bg-[var(--paper-0)] hover:bg-[var(--paper-2)] transition-colors">
            Cancel
          </button>
          <button @click="commitAddRef"
                  :disabled="!newRefTitle.trim() || !newRefPointer.trim()"
                  class="text-[10px] font-semibold text-white bg-[var(--ember)] px-2.5 py-1 rounded-[var(--r-sm)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity">
            Add
          </button>
        </div>
      </div>
    </div>

    <!-- Diff modal -->
    <AgentSoulDiffModal v-if="showDiff"
      :published="props.profile.published_soul ?? ''"
      :current="localSoul"
      @close="showDiff = false"
    />

    <!-- Revise modal -->
    <AgentSoulReviseModal v-if="showRevise && reviseSuggestion"
      :suggestion="reviseSuggestion"
      :original="localSoul"
      @accept="onAcceptRevision"
      @discard="showRevise = false"
      @close="showRevise = false"
    />

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import type { AgentProfileData, StyleRef } from '~/composables/useAgentProfile'
import { estimateCallCost } from '~/utils/llmPricing'

const props = defineProps<{
  profile: AgentProfileData
  saving: boolean
  reviseSoul: (soul: string) => Promise<string | null>
}>()

const emit = defineEmits<{
  (e: 'update', section: string, fields: Partial<AgentProfileData>): void
}>()

const localSoul = ref(props.profile.soul ?? '')
const localRefs = reactive<StyleRef[]>([...(props.profile.style_references ?? [])])

watch(() => props.profile, (next) => {
  if (!next) return
  localSoul.value = next.soul ?? ''
  localRefs.splice(0, localRefs.length, ...(next.style_references ?? []))
})

const lineCount    = computed(() => localSoul.value.split('\n').length)
const tokenEstimate = computed(() => Math.ceil(localSoul.value.length / 4).toLocaleString())
const costEstimate  = computed(() => estimateCallCost(props.profile.default_model, localSoul.value.length))

// "saved Xs ago" timer
const lastSavedAt = ref<number | null>(null)
const nowTs       = ref(Date.now())

watch(() => props.saving, (isSaving, wasSaving) => {
  if (wasSaving && !isSaving) lastSavedAt.value = Date.now()
})

const savedLabel = computed(() => {
  if (!lastSavedAt.value) return 'saved'
  const secs = Math.floor((nowTs.value - lastSavedAt.value) / 1000)
  if (secs < 5)  return 'just saved'
  if (secs < 60) return `saved ${secs}s ago`
  return `saved ${Math.floor(secs / 60)}m ago`
})

let _ticker: ReturnType<typeof setInterval> | null = null
onMounted(() => { _ticker = setInterval(() => { nowTs.value = Date.now() }, 1000) })
onUnmounted(() => { if (_ticker) clearInterval(_ticker) })

// Diff
const showDiff        = ref(false)
const hasPublishedDiff = computed(() =>
  !!(props.profile.published_soul !== null && props.profile.published_soul !== localSoul.value)
)

// Revise
const revising         = ref(false)
const showRevise       = ref(false)
const reviseSuggestion = ref<string | null>(null)

async function onRevise() {
  revising.value = true
  reviseSuggestion.value = null
  const result = await props.reviseSoul(localSoul.value)
  revising.value = false
  if (result) {
    reviseSuggestion.value = result
    showRevise.value = true
  }
}

function onAcceptRevision(suggestion: string) {
  localSoul.value = suggestion
  showRevise.value = false
  onSoulChange()
}

// Soul editing
function onSoulChange() {
  emit('update', 'soul', { soul: localSoul.value, style_references: [...localRefs] })
}

// Style references
const addingRef      = ref(false)
const newRefType     = ref<'link' | 'doc'>('link')
const newRefTitle    = ref('')
const newRefPointer  = ref('')
const refTitleInputRef = ref<HTMLInputElement | null>(null)

function startAddRef() {
  addingRef.value = true
  newRefType.value = 'link'
  newRefTitle.value = ''
  newRefPointer.value = ''
  nextTick(() => refTitleInputRef.value?.focus())
}

function cancelAddRef() {
  addingRef.value = false
}

function commitAddRef() {
  const title   = newRefTitle.value.trim()
  const pointer = newRefPointer.value.trim()
  if (!title || !pointer) return
  localRefs.push({ type: newRefType.value, title, pointer })
  emit('update', 'soul', { soul: localSoul.value, style_references: [...localRefs] })
  addingRef.value = false
}

function removeRef(idx: number) {
  localRefs.splice(idx, 1)
  emit('update', 'soul', { soul: localSoul.value, style_references: [...localRefs] })
}
</script>
