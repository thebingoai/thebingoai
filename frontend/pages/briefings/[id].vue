<template>
  <div class="h-full overflow-y-auto bg-white dark:bg-neutral-900">
    <!-- Loading skeleton -->
    <div v-if="loading" class="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <div class="h-3 w-40 bg-neutral-200 rounded animate-pulse" />
      <div class="h-10 w-3/4 bg-neutral-200 rounded animate-pulse" />
      <div class="h-4 w-full bg-neutral-100 rounded animate-pulse" />
      <div class="h-4 w-5/6 bg-neutral-100 rounded animate-pulse" />
    </div>

    <!-- API error / not found (briefing is null) -->
    <div v-else-if="!briefing && error" class="max-w-3xl mx-auto px-6 py-10">
      <div class="rounded-lg border border-rose-200 bg-rose-50 p-6">
        <h2 class="text-lg font-semibold text-rose-900 mb-2">Could not load briefing</h2>
        <p class="text-sm text-rose-700">{{ error }}</p>
      </div>
    </div>

    <!-- Failed (briefing exists but status is failed) -->
    <div v-else-if="briefing.status === 'failed'" class="max-w-3xl mx-auto px-6 py-10">
      <div class="rounded-lg border border-rose-200 bg-rose-50 p-6">
        <h2 class="text-lg font-semibold text-rose-900 mb-2">Briefing failed</h2>
        <p class="text-sm text-rose-700 mb-4">{{ briefing.error || 'Unknown error.' }}</p>
        <button class="px-3 py-1.5 rounded bg-rose-600 text-white text-sm" @click="retry">Retry</button>
      </div>
    </div>

    <!-- Ready -->
    <article v-else class="max-w-3xl mx-auto px-6 py-10">
      <div class="flex justify-end gap-2 mb-6">
        <button
          class="text-xs px-3 py-1 rounded-full border border-neutral-200 dark:border-neutral-700 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
          @click="copyLink"
        >
          Copy link
        </button>
      </div>

      <p class="text-xs uppercase tracking-wider text-neutral-500 mb-3">
        Dashboard #{{ briefing.dashboard_id }}
        <template v-if="briefing.date_range_from"> &middot; {{ formatRange(briefing) }}</template>
      </p>

      <h1 class="font-serif text-4xl font-bold leading-tight text-neutral-900 dark:text-neutral-100 mb-5 tracking-tight">
        {{ briefing.payload!.headline }}
      </h1>

      <div
        class="flex items-center gap-3 text-sm text-neutral-600 dark:text-neutral-400 mb-5 pb-4 border-b border-neutral-100 dark:border-neutral-800"
      >
        <div class="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-pink-500" />
        <span><strong>Compiled by Bingo</strong> &middot; {{ formatDate(briefing.created_at) }}</span>
      </div>

      <p class="text-lg leading-relaxed text-neutral-800 dark:text-neutral-200 mb-6">
        {{ briefing.payload!.deck }}
      </p>

      <div
        v-if="briefing.payload!.kpis.length"
        class="grid gap-3 p-4 bg-neutral-50 dark:bg-neutral-800 rounded-lg mb-7"
        :style="{ gridTemplateColumns: `repeat(${briefing.payload!.kpis.length}, minmax(0,1fr))` }"
      >
        <div
          v-for="(k, i) in briefing.payload!.kpis"
          :key="i"
          class="pl-3"
          :class="{ 'border-l border-neutral-200 dark:border-neutral-700': i > 0 }"
        >
          <div class="text-[11px] uppercase tracking-wide text-neutral-500">{{ k.label }}</div>
          <div class="text-2xl font-semibold mt-1">{{ k.value }}</div>
          <div v-if="k.delta_vs_prev" class="text-xs mt-1" :class="deltaClass(k.delta_direction)">
            {{ k.delta_vs_prev }}
          </div>
        </div>
      </div>

      <section v-for="(s, idx) in briefing.payload!.sections" :key="idx" class="mb-7">
        <h2 class="font-serif text-2xl font-bold text-neutral-900 dark:text-neutral-100 mb-3">
          <span class="text-neutral-400 font-normal mr-2">{{ idx + 1 }}.</span>{{ s.heading }}
        </h2>
        <div class="text-[15px] leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
          {{ s.prose }}
        </div>
        <BriefingWidgetEmbed
          v-if="s.widget_id"
          :widget-id="s.widget_id"
          :dashboard-id="briefing.dashboard_id"
          class="mt-4"
        />
      </section>

      <aside
        class="rounded-lg bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 p-5 mt-4"
      >
        <p class="text-[11px] uppercase tracking-wider font-semibold text-yellow-900 dark:text-yellow-200 mb-2">
          Key takeaways
        </p>
        <ul class="list-disc pl-5 space-y-1 text-yellow-950 dark:text-yellow-200">
          <li v-for="(t, i) in briefing.payload!.key_takeaways" :key="i" class="text-sm">{{ t }}</li>
        </ul>
      </aside>
    </article>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const briefingId = computed(() => parseInt(route.params.id as string))
const { briefing, loading, refresh } = useBriefing(briefingId)

function deltaClass(dir?: 'up' | 'down' | 'flat' | null) {
  if (dir === 'up') return 'text-emerald-600'
  if (dir === 'down') return 'text-rose-600'
  return 'text-neutral-500'
}

function formatRange(b: any) {
  if (!b.date_range_from || !b.date_range_to) return ''
  const from = new Date(b.date_range_from).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
  const to = new Date(b.date_range_to).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
  return `${from} – ${to}`
}

function formatDate(s: string) {
  return new Date(s).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function copyLink() {
  await navigator.clipboard.writeText(window.location.href)
}

async function retry() {
  if (!briefing.value) return
  const { fetchWithRefresh } = useApi()
  const resp = await fetchWithRefresh(`/api/dashboards/${briefing.value.dashboard_id}/brief`, {
    method: 'POST',
  })
  if (resp?.briefing_id && resp.briefing_id !== briefing.value.id) {
    await navigateTo(`/briefings/${resp.briefing_id}`)
  } else {
    await refresh()
  }
}

</script>
