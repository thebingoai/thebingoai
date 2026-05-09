<template>
  <div id="identity" class="border border-[var(--line)] rounded-[var(--r-lg)] p-6">

    <!-- Section header -->
    <div class="flex items-start justify-between mb-5">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-[var(--r-sm)] bg-[var(--ember-wash)] border border-[color-mix(in_oklch,var(--ember)_20%,var(--line))] flex items-center justify-center text-base flex-shrink-0">
          ⚡
        </div>
        <div>
          <h2 class="font-serif italic text-xl font-bold text-[var(--ember)]">Identity</h2>
          <p class="text-[11px] text-[var(--ink-2)] mt-0.5 leading-snug max-w-md">
            The name and voice the model presents with. Affects greeting, signature, and how the agent introduces itself in new threads or scheduled digests.
          </p>
        </div>
      </div>
      <span class="text-[10px] font-semibold px-2.5 py-1 rounded-full border"
        :class="isPublished
          ? 'text-[var(--ok)] bg-[oklch(0.97_0.04_150)] border-[oklch(0.88_0.08_150)]'
          : 'text-[var(--ink-2)] bg-[var(--paper-2)] border-[var(--line)]'">
        {{ isPublished ? '✓ published' : 'draft' }}
      </span>
    </div>

    <!-- Avatar row -->
    <div class="flex items-center gap-4 pb-5 mb-5 border-b border-[var(--line)]">
      <div class="w-13 h-13 rounded-[var(--r-md)] bg-[var(--ink-0)] flex items-center justify-center text-white font-bold text-xl font-serif italic flex-shrink-0 overflow-hidden"
           style="width:52px;height:52px;">
        <img v-if="localData.avatar_url" :src="localData.avatar_url" class="w-full h-full object-cover" alt="Avatar" />
        <span v-else>{{ avatarInitial }}</span>
      </div>
      <div class="flex-1">
        <p class="text-sm font-semibold text-[var(--ink-0)]">{{ localData.display_name || 'Bingo' }}</p>
        <p class="text-[10px] text-[var(--ink-3)] mt-0.5">Avatar shown in chat, digests, dashboards</p>
      </div>
      <div class="flex gap-2">
        <label class="text-[11px] font-medium border border-[var(--line-2)] text-[var(--ink-1)] px-3 py-1.5 rounded-[var(--r-sm)] cursor-pointer bg-[var(--paper-0)] hover:bg-[var(--paper-2)] transition-colors">
          Replace avatar
          <input type="file" accept="image/*" class="hidden" @change="onAvatarFile" />
        </label>
        <button v-if="localData.avatar_url"
                class="text-[11px] text-[var(--ink-2)] px-3 py-1.5 rounded-[var(--r-sm)] hover:bg-[var(--paper-2)] transition-colors"
                @click="resetAvatar">
          Restore default
        </button>
      </div>
    </div>

    <!-- Name + Pronouns -->
    <div class="grid grid-cols-2 gap-5 mb-5">
      <div>
        <label class="block text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1.5">Name</label>
        <input v-model="localData.display_name" @input="onIdentityChange"
               class="w-full border-0 border-b border-[var(--line)] pb-1.5 text-[13px] text-[var(--ink-0)] bg-transparent outline-none focus:border-[var(--ember)] transition-colors" />
        <p class="text-[9px] text-[var(--ink-3)] mt-1">Used in greetings · email signatures · push titles</p>
      </div>
      <div>
        <label class="block text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1.5">Pronouns</label>
        <input v-model="localData.pronouns" @input="onIdentityChange"
               class="w-full border-0 border-b border-[var(--line)] pb-1.5 text-[13px] text-[var(--ink-0)] bg-transparent outline-none focus:border-[var(--ember)] transition-colors" />
      </div>
    </div>

    <!-- Tagline + Model -->
    <div class="grid grid-cols-2 gap-5 mb-5">
      <div>
        <label class="block text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1.5">Tagline</label>
        <input v-model="localData.tagline" @input="onIdentityChange"
               class="w-full border-0 border-b border-[var(--line)] pb-1.5 text-[13px] text-[var(--ink-0)] bg-transparent outline-none focus:border-[var(--ember)] transition-colors" />
        <p class="text-[9px] text-[var(--ink-3)] mt-1">Shown under the name on first run</p>
      </div>
      <div>
        <label class="block text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1.5">Default Model</label>
        <select v-model="localData.default_model" @change="onIdentityChange"
                class="w-full border-0 border-b border-[var(--line)] pb-1.5 text-[13px] text-[var(--ink-0)] bg-transparent outline-none focus:border-[var(--ember)] transition-colors">
          <!-- Empty / "use system default" -->
          <option value="">
            System default{{ models?.default_model ? ` (${models.default_model})` : '' }}
          </option>
          <!-- Real models grouped by provider -->
          <optgroup v-for="provider in availableProviders" :key="provider.name"
                    :label="provider.name">
            <option v-for="m in provider.models" :key="m" :value="m">{{ m }}</option>
          </optgroup>
          <!-- Stale value still selected: keep visible so user sees what's saved -->
          <option v-if="staleSelectedModel" :value="localData.default_model">
            {{ localData.default_model }} (not currently available)
          </option>
        </select>
      </div>
    </div>

    <!-- Temperature + Max tokens -->
    <div class="grid grid-cols-2 gap-5">
      <div>
        <label class="block text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1.5">Temperature</label>
        <div class="flex items-center gap-3 mt-1.5">
          <input type="range" min="0" max="1" step="0.05"
                 v-model.number="localData.temperature" @input="onIdentityChange"
                 class="flex-1 accent-[var(--ember)] h-1 cursor-pointer" />
          <span class="text-[13px] font-semibold text-[var(--ink-1)] font-mono w-8 text-right">
            {{ localData.temperature?.toFixed(2) ?? '0.40' }}
          </span>
        </div>
        <div class="flex justify-between mt-1">
          <span class="text-[9px] text-[var(--ink-3)]">0 = deterministic</span>
          <span class="text-[9px] text-[var(--ink-3)]">1 = exploratory</span>
        </div>
      </div>
      <div>
        <label class="block text-[9.5px] font-bold tracking-[.08em] uppercase text-[var(--ink-3)] mb-1.5">Max Output Tokens</label>
        <input v-model.number="localData.max_output_tokens" @input="onIdentityChange"
               type="number" min="256" max="32768"
               class="w-full border-0 border-b border-[var(--line)] pb-1.5 text-[13px] text-[var(--ink-0)] bg-transparent outline-none focus:border-[var(--ember)] transition-colors" />
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { reactive, computed, watch } from 'vue'
import type { AgentProfileData, ModelsResponse } from '~/composables/useAgentProfile'

const props = defineProps<{
  profile: AgentProfileData
  isPublished: boolean
  models: ModelsResponse | null
}>()

const emit = defineEmits<{
  (e: 'update', section: string, fields: Partial<AgentProfileData>): void
  (e: 'avatar-file', file: File): void
}>()

const localData = reactive({
  display_name:      props.profile.display_name      ?? '',
  pronouns:          props.profile.pronouns          ?? '',
  tagline:           props.profile.tagline           ?? '',
  avatar_url:        props.profile.avatar_url        ?? null,
  default_model:     props.profile.default_model     ?? 'claude-sonnet-4-6',
  temperature:       props.profile.temperature       ?? 0.4,
  max_output_tokens: props.profile.max_output_tokens ?? 4096,
})

// Server-pushed avatar mutations (upload) need to flow into localData
watch(() => props.profile.avatar_url, (next) => {
  localData.avatar_url = next ?? null
})

// Whole-profile replacement (e.g. reset to published snapshot) — sync everything
watch(() => props.profile, (next) => {
  if (!next) return
  localData.display_name      = next.display_name      ?? ''
  localData.pronouns          = next.pronouns          ?? ''
  localData.tagline           = next.tagline           ?? ''
  localData.avatar_url        = next.avatar_url        ?? null
  localData.default_model     = next.default_model     ?? ''
  localData.temperature       = next.temperature       ?? 0.4
  localData.max_output_tokens = next.max_output_tokens ?? 4096
})

const avatarInitial = computed(() =>
  (localData.display_name?.[0] ?? 'B').toUpperCase()
)

const availableProviders = computed(() =>
  (props.models?.providers ?? []).filter(p => p.available && p.models.length > 0)
)

// True when the saved value isn't blank, isn't in any current provider list,
// and isn't the system default — surface it so the user can see what's stored.
const staleSelectedModel = computed(() => {
  const v = localData.default_model
  if (!v) return false
  const known = new Set(availableProviders.value.flatMap(p => p.models))
  return !known.has(v)
})

function onIdentityChange() {
  emit('update', 'identity', {
    display_name:      localData.display_name,
    pronouns:          localData.pronouns,
    tagline:           localData.tagline,
    default_model:     localData.default_model,
    temperature:       localData.temperature,
    max_output_tokens: localData.max_output_tokens,
  })
}

function onAvatarFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('avatar-file', file)
}

function resetAvatar() {
  localData.avatar_url = null
  emit('update', 'identity', { avatar_url: null })
}
</script>
