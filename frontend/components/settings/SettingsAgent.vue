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
        @history="showHistory = true"
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
            @avatar-file="agentProfile.uploadAvatar"
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

    <!-- History drawer (stub for v1) -->
    <div v-if="showHistory"
         class="fixed inset-0 bg-black/30 z-50 flex items-end justify-center"
         @click.self="showHistory = false">
      <div class="bg-[var(--paper-0)] rounded-t-[var(--r-lg)] p-6 w-full max-w-lg">
        <h3 class="font-semibold text-[var(--ink-0)] mb-2">Publish History</h3>
        <p class="text-sm text-[var(--ink-2)]">
          {{ agentProfile.profile.value?.published_at
            ? `Last published: ${new Date(agentProfile.profile.value.published_at).toLocaleString()}`
            : 'No publish history yet.' }}
        </p>
        <button @click="showHistory = false"
                class="mt-4 text-sm font-medium text-[var(--ember)] hover:opacity-80">
          Close
        </button>
      </div>
    </div>

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

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAgentProfile } from '~/composables/useAgentProfile'

const agentProfile     = useAgentProfile()
const docScrollRef     = ref<HTMLElement | null>(null)
const activeSection    = ref('identity')
const showHistory      = ref(false)
const showResetConfirm = ref(false)

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

const sectionIds = ['identity', 'soul', 'user-context']

function onScroll() {
  if (!docScrollRef.value) return
  const scrollTop = docScrollRef.value.scrollTop + 80
  let current = sectionIds[0]
  for (const id of sectionIds) {
    const el = document.getElementById(id)
    if (el && el.offsetTop <= scrollTop) current = id
  }
  activeSection.value = current
}

onMounted(() => {
  agentProfile.fetchProfile()
  agentProfile.fetchModels()
})
</script>
