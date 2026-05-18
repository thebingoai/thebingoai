<template>
  <div class="flex flex-col h-full overflow-hidden">

    <!-- Page header -->
    <div class="px-7 pt-[18px] pb-4 border-b border-[var(--line)] flex-shrink-0">
      <p class="text-[10px] font-semibold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1">
        Settings · The thing you talk to
      </p>
      <h1 class="text-[28px] font-bold text-[var(--ink-0)] tracking-tight leading-none">Agent</h1>
    </div>

    <!-- Body: rail + document -->
    <div class="flex flex-1 overflow-hidden">

      <!-- Left anchor rail (scroll-spy driven) -->
      <AgentPublishRail
        :active-section="activeSection"
        :version-label="agentProfile.versionLabel.value"
        :publishing="agentProfile.publishing.value"
        :resetting="agentProfile.resetting.value"
        :can-reset="canReset"
        :scroll-container="docScrollRef"
        @publish="agentProfile.publish()"
        @reset="onReset"
        @factory-reset="onFactoryReset"
        @navigate="onRailNavigate"
      />

      <!-- Scrollable document -->
      <div ref="docScrollRef" class="flex-1 overflow-y-auto px-9 py-7" @scroll="onScroll">

        <!-- Intro card -->
        <div class="bg-[var(--ember-wash)] border border-[color-mix(in_oklch,var(--ember)_20%,var(--line))] rounded-[var(--r-lg)] px-7 py-6 mb-6">
          <p class="text-[9.5px] font-bold tracking-[.1em] uppercase text-[var(--ink-3)] mb-2">The Agent</p>
          <h2 class="text-2xl font-bold text-[var(--ink-0)] mb-3 leading-snug">
            <em class="font-serif italic text-[var(--ember)]]">{{ agentName }}</em> is a document.
          </h2>
          <p class="text-xs text-[var(--ink-2)] leading-relaxed mb-4 max-w-2xl">
            Identity is who it is. Soul is how it thinks. User context is everything it knows about the person on the other end. Edit any section — the rest stays consistent.
          </p>
          <div class="flex items-center gap-2 flex-wrap">
            <span class="text-[10px] font-semibold px-2.5 py-1 rounded-full border bg-[color-mix(in_oklch,var(--ember)_12%,var(--paper-0))] border-[color-mix(in_oklch,var(--ember)_30%,var(--line))] text-[var(--ember)]">
              ✦ {{ agentProfile.versionLabel.value }} · {{ agentProfile.isDraft.value ? 'draft' : 'published' }}
            </span>
            <span class="text-[10px] px-2.5 py-1 rounded-full border border-[var(--line)] bg-[var(--paper-0)] text-[var(--ink-2)]">
              {{ agentProfile.lastPublishedLabel.value }}
            </span>
            <span v-if="agentProfile.changedCount.value > 0"
                  class="text-[10px] px-2.5 py-1 rounded-full border border-[var(--line)] bg-[var(--paper-0)] text-[var(--ink-2)]">
              {{ agentProfile.changedCount.value }} section{{ agentProfile.changedCount.value > 1 ? 's' : '' }} changed
            </span>
          </div>
        </div>

        <!-- Loading state -->
        <div v-if="agentProfile.loading.value" class="flex items-center justify-center py-16 text-[var(--ink-3)] text-sm">
          Loading…
        </div>

        <template v-else-if="agentProfile.profile.value">
          <AgentIdentitySection
            :profile="agentProfile.profile.value"
            :is-published="!agentProfile.isDraft.value"
            :models="agentProfile.models.value"
            class="mb-6"
            @update="agentProfile.updateField"
          />
          <AgentSoulSection
            :profile="agentProfile.profile.value"
            :saving="agentProfile.saving.value"
            class="mb-6"
            @update="agentProfile.updateField"
          />
          <AgentUserContextSection
            :profile="agentProfile.profile.value"
            class="mb-6"
            @update="agentProfile.updateField"
          />
        </template>

      </div><!-- /doc-scroll -->
    </div><!-- /body -->

    <!-- Reset draft confirmation -->
    <div v-if="showResetConfirm"
         class="fixed inset-0 bg-black/30 z-50 flex items-center justify-center"
         @click.self="showResetConfirm = false"
         @keydown.esc="showResetConfirm = false">
      <div class="bg-[var(--paper-0)] border border-[var(--line)] rounded-[var(--r-lg)] p-6 w-full max-w-md shadow-xl">
        <h3 class="font-serif italic text-lg font-bold text-[var(--ember)] mb-1">Discard draft changes?</h3>
        <p class="text-[12px] text-[var(--ink-2)] leading-relaxed mb-4">
          Every unpublished edit since the last publish will be reverted. This can't be undone.
        </p>
        <div class="flex justify-end gap-2">
          <button @click="showResetConfirm = false"
                  class="text-[11px] font-medium border border-[var(--line)] text-[var(--ink-1)] px-3 py-1.5 rounded-[var(--r-sm)] bg-[var(--paper-0)] hover:bg-[var(--paper-2)] transition-colors">
            Keep editing
          </button>
          <button @click="confirmReset"
                  :disabled="agentProfile.resetting.value"
                  class="text-[11px] font-semibold text-white bg-[var(--ember)] px-3 py-1.5 rounded-[var(--r-sm)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity">
            {{ agentProfile.resetting.value ? 'Reverting…' : 'Discard changes' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Factory reset confirmation -->
    <div v-if="showFactoryResetConfirm"
         class="fixed inset-0 bg-black/30 z-50 flex items-center justify-center"
         @click.self="showFactoryResetConfirm = false"
         @keydown.esc="showFactoryResetConfirm = false">
      <div class="bg-[var(--paper-0)] border border-[var(--line)] rounded-[var(--r-lg)] p-6 w-full max-w-md shadow-xl">
        <h3 class="font-serif italic text-lg font-bold text-[var(--ember)] mb-1">Revert to Bingo default?</h3>
        <p class="text-[12px] text-[var(--ink-2)] leading-relaxed mb-4">
          This wipes every Identity, Soul, and User-context customization — including avatar, name, model overrides, and any saved profile facts — and immediately republishes the defaults so new chats reflect the reset. This can't be undone.
        </p>
        <div class="flex justify-end gap-2">
          <button @click="showFactoryResetConfirm = false"
                  class="text-[11px] font-medium border border-[var(--line)] text-[var(--ink-1)] px-3 py-1.5 rounded-[var(--r-sm)] bg-[var(--paper-0)] hover:bg-[var(--paper-2)] transition-colors">
            Keep my customizations
          </button>
          <button @click="confirmFactoryReset"
                  :disabled="agentProfile.resetting.value"
                  class="text-[11px] font-semibold text-white bg-[var(--ember)] px-3 py-1.5 rounded-[var(--r-sm)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed transition-opacity">
            {{ agentProfile.resetting.value ? 'Reverting…' : 'Revert to default' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAgentProfile } from '~/composables/useAgentProfile'

const agentProfile          = useAgentProfile()
const docScrollRef          = ref<HTMLElement | null>(null)
const activeSection         = ref('identity')
const showResetConfirm      = ref(false)
const showFactoryResetConfirm = ref(false)

const agentName = computed(() =>
  agentProfile.profile.value?.display_name || 'Bingo'
)

// Reset is only meaningful once there is something published to revert to,
// AND the current state has unsaved drafted changes since that publish.
const canReset = computed(() =>
  !!agentProfile.profile.value?.published_version && agentProfile.isDraft.value
)

function onReset() {
  showResetConfirm.value = true
}

async function confirmReset() {
  await agentProfile.resetDraft()
  showResetConfirm.value = false
}

function onFactoryReset() {
  showFactoryResetConfirm.value = true
}

async function confirmFactoryReset() {
  await agentProfile.factoryReset()
  showFactoryResetConfirm.value = false
}

const sectionIds = ['identity', 'soul', 'user-context']

// While the rail's programmatic smooth-scroll is animating, ignore scroll-spy
// — otherwise the highlight flickers across every section it passes through.
let suppressScrollSpyUntil = 0

function onRailNavigate(id: string) {
  activeSection.value = id
  suppressScrollSpyUntil = Date.now() + 700
}

function onScroll() {
  if (Date.now() < suppressScrollSpyUntil) return
  const container = docScrollRef.value
  if (!container) return
  const scrollTop = container.scrollTop
  const maxScroll = container.scrollHeight - container.clientHeight
  // When pinned at the bottom, the last section is what's visible — its
  // offsetTop is below maxScroll so the standard check would miss it.
  if (maxScroll > 0 && scrollTop >= maxScroll - 2) {
    activeSection.value = sectionIds[sectionIds.length - 1]
    return
  }
  const offset = scrollTop + 80
  let current = sectionIds[0]
  for (const id of sectionIds) {
    const el = document.getElementById(id)
    if (el && el.offsetTop <= offset) current = id
  }
  activeSection.value = current
}

onMounted(() => {
  agentProfile.fetchProfile()
  agentProfile.fetchModels()
})
</script>
