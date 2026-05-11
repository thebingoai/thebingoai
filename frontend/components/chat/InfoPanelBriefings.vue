<template>
  <div>
    <div v-if="loading" class="text-[13px] text-[var(--ink-2)] py-4 text-center">
      Loading briefings…
    </div>

    <div v-else-if="error" class="text-[13px] text-red-500 py-4 text-center">
      {{ error }}
    </div>

    <div v-else-if="!briefings.length" class="text-[13px] text-[var(--ink-2)] py-8 text-center">
      <p class="mb-1">No briefings yet</p>
      <p class="text-[11px]">Open a dashboard and click "Brief me" to get started.</p>
    </div>

    <template v-else>
      <template v-for="group in groups" :key="group.label || '__recent__'">
        <p v-if="group.label" class="px-0.5 pt-2 pb-1 text-[10px] font-semibold tracking-widest uppercase text-[var(--ink-2)]">
          {{ group.label }}
        </p>

        <template v-for="b in group.items" :key="b.id">
          <!-- Expanded card (active/selected briefing, expands in place) -->
          <div
            v-if="b.id === activeId"
            class="briefing-expand rounded-xl border border-violet-300 dark:border-violet-700 bg-[var(--paper-0)] p-3.5 mb-1.5 cursor-pointer shadow-sm"
            @click="openBriefing(b.id)"
          >
            <div class="flex items-start gap-2.5">
              <span
                class="mt-0.5 flex-shrink-0 w-2.5 h-2.5 rounded-full"
                :class="{
                  'bg-violet-600': b.status === 'ready',
                  'bg-amber-400': b.status === 'generating',
                  'bg-rose-400': b.status === 'failed',
                }"
              />
              <div class="flex-1 min-w-0">
                <p class="text-[13px] font-semibold text-[var(--ink-0)] leading-snug">
                  {{ b.payload?.headline || 'Generating briefing…' }}
                </p>
                <p v-if="b.payload?.deck" class="mt-1 text-[12px] text-[var(--ink-2)] leading-relaxed line-clamp-2">
                  {{ b.payload.deck }}
                </p>
                <p v-else-if="b.status === 'generating'" class="mt-1 text-[12px] text-amber-500">
                  Generating…
                </p>
                <p class="mt-2 text-[11px] text-[var(--ink-2)]">
                  {{ formatRelative(b.created_at) }}
                  <template v-if="b.trigger === 'scheduled'">
                    <span class="mx-1">·</span>auto
                  </template>
                </p>
              </div>
            </div>
          </div>

          <!-- Compact row (all other briefings) -->
          <button
            v-else
            class="briefing-collapse relative w-full flex items-center gap-1.5 py-1.5 pl-1.5 pr-20 rounded-lg hover:bg-[var(--paper-2)] transition-colors text-left"
            @click="openBriefing(b.id)"
          >
            <Newspaper
              class="flex-shrink-0 w-3.5 h-3.5"
              :class="b.status === 'ready' ? 'text-violet-400' : 'text-[var(--ink-2)]'"
            />
            <span class="min-w-0 truncate text-[12.5px] text-[var(--ink-1)]">
              {{ b.payload?.headline || 'Untitled briefing' }}
            </span>
            <span class="absolute right-1.5 text-[11px] text-[var(--ink-2)] tabular-nums">
              {{ formatShort(b.created_at) }}
            </span>
          </button>
        </template>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Newspaper } from 'lucide-vue-next'

const { fetchWithRefresh } = useApi()
const briefings = ref<any[]>([])
const loading = ref(true)
const error = ref('')

async function load() {
  try {
    loading.value = true
    briefings.value = await fetchWithRefresh('/api/briefings?limit=50', { method: 'GET' })
    error.value = ''
  } catch (e: any) {
    error.value = e?.message || 'Failed to load briefings'
  } finally {
    loading.value = false
  }
}

const { id: activeId, open: openBriefing } = useActiveBriefing()

onMounted(load)

const groups = computed(() => {
  if (!briefings.value.length) return []

  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - 1)
  cutoff.setHours(0, 0, 0, 0)

  const recent: any[] = []
  const earlier: any[] = []

  for (const b of briefings.value) {
    if (new Date(b.created_at) >= cutoff) recent.push(b)
    else earlier.push(b)
  }

  const result: { label: string; items: any[] }[] = []
  if (recent.length) result.push({ label: '', items: recent })
  if (earlier.length) result.push({ label: 'Earlier', items: earlier })
  return result
})

function formatRelative(s: string) {
  const diffMs = Date.now() - new Date(s).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  if (hours < 48) return 'yesterday'
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatShort(s: string) {
  const diffMs = Date.now() - new Date(s).getTime()
  const mins = Math.floor(diffMs / 60000)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(diffMs / 3600000)
  if (hours < 24) return `${hours}h`
  if (hours < 48) return 'yesterday'
  return new Date(s).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
@keyframes expand-in {
  from {
    opacity: 0;
    transform: scaleY(0.75);
    transform-origin: top;
  }
  to {
    opacity: 1;
    transform: scaleY(1);
    transform-origin: top;
  }
}

@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.briefing-expand {
  animation: expand-in 0.2s ease-out forwards;
}

.briefing-collapse {
  animation: fade-in 0.15s ease-out forwards;
}
</style>
