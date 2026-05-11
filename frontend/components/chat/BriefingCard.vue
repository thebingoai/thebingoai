<template>
  <div class="rounded-xl border border-[var(--line)] bg-[var(--paper-0)] overflow-hidden text-left">

    <!-- Loading -->
    <div v-if="loading" class="flex items-center gap-2 p-4 text-[13px] text-[var(--ink-2)]">
      <Loader2 class="h-4 w-4 animate-spin" />
      <span>Loading briefing…</span>
    </div>

    <!-- Generating -->
    <div v-else-if="briefing?.status === 'generating'" class="flex items-center gap-2 p-4 text-[13px] text-[var(--ink-2)]">
      <Loader2 class="h-4 w-4 animate-spin text-violet-500" />
      <span>Briefing generating…</span>
    </div>

    <!-- Failed -->
    <div v-else-if="briefing?.status === 'failed'" class="p-4 text-[13px] text-red-500">
      {{ briefing.error || 'Briefing generation failed.' }}
    </div>

    <!-- Error -->
    <div v-else-if="error" class="p-4 text-[13px] text-red-500">{{ error }}</div>

    <!-- Ready -->
    <template v-else-if="briefing?.status === 'ready' && briefing.payload">

      <!-- Header: label + headline + deck -->
      <div class="px-5 pt-4 pb-3">
        <p class="text-[10px] font-semibold tracking-widest uppercase text-[var(--ink-2)] mb-1.5">
          Briefing{{ briefing.dashboard_name ? ` · ${briefing.dashboard_name}` : '' }}
        </p>
        <h3 class="text-[17px] font-bold text-[var(--ink-0)] leading-snug">
          {{ briefing.payload.headline }}
        </h3>
        <p class="mt-1 text-[13px] text-[var(--ink-2)] leading-relaxed">
          {{ briefing.payload.deck }}
        </p>
      </div>

      <div class="border-t border-dashed border-[var(--line)]" />

      <!-- KPIs -->
      <div v-if="briefing.payload.kpis.length" class="px-4 py-3 flex gap-2.5">
        <div
          v-for="(kpi, i) in briefing.payload.kpis"
          :key="kpi.label"
          class="flex-1 min-w-0 rounded-lg border border-[var(--line)] px-3 py-2.5"
          :style="{ borderLeftWidth: '3px', borderLeftColor: kpiColor(kpi, i) }"
        >
          <div class="text-[9px] font-semibold tracking-widest uppercase text-[var(--ink-2)] truncate">{{ kpi.label }}</div>
          <div class="text-[15px] font-bold text-[var(--ink-0)] mt-0.5 tabular-nums">{{ kpi.value }}</div>
          <div
            v-if="kpi.delta_vs_prev"
            class="text-[11px] font-medium mt-0.5 tabular-nums"
            :style="{ color: kpiColor(kpi, i) }"
          >
            {{ kpi.delta_vs_prev }}
          </div>
        </div>
      </div>

      <div class="border-t border-dashed border-[var(--line)]" />

      <!-- First section preview -->
      <div v-if="briefing.payload.sections.length" class="px-5 py-3">
        <p class="text-[13px] font-semibold text-[var(--ink-0)]">
          {{ stripLeadingNumber(briefing.payload.sections[0].heading) }}
        </p>
        <p class="mt-1 text-[13px] text-[var(--ink-2)] leading-relaxed line-clamp-3">
          {{ briefing.payload.sections[0].prose }}
        </p>
        <button
          v-if="briefing.payload.sections.length > 1"
          class="mt-2 text-[12px] text-[var(--ink-2)] hover:text-[var(--ink-0)] transition-colors"
          @click="open(briefing!.id)"
        >
          + {{ briefing.payload.sections.length - 1 }} more findings · continue reading →
        </button>
      </div>

      <div class="border-t border-dashed border-[var(--line)]" />

      <!-- Footer -->
      <div class="px-5 py-3 flex items-center justify-between gap-3">
        <span class="text-[11px] text-[var(--ink-2)]">
          {{ briefing.payload.kpis.length }} KPIs · {{ briefing.payload.sections.length }} sections · {{ briefing.payload.key_takeaways.length }} takeaways
        </span>
        <button
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--ink-0)] text-[var(--paper-0)] text-[12px] font-medium hover:opacity-80 transition-opacity flex-shrink-0"
          @click="open(briefing!.id)"
        >
          <Newspaper class="h-3.5 w-3.5" />
          Read full briefing
        </button>
      </div>

    </template>
  </div>
</template>

<script setup lang="ts">
import { Loader2, Newspaper } from 'lucide-vue-next'
import type { BriefingKpi } from '~/composables/useBriefing'

const props = defineProps<{ briefingId: number }>()

const { briefing, loading, error } = useBriefing(toRef(props, 'briefingId'))
const { open } = useActiveBriefing()

const KPI_COLORS = ['#22c55e', '#ef4444', '#7c3aed']

function kpiColor(kpi: BriefingKpi, index: number): string {
  if (kpi.delta_direction === 'up') return '#22c55e'
  if (kpi.delta_direction === 'down') return '#ef4444'
  return KPI_COLORS[index % KPI_COLORS.length]
}

function stripLeadingNumber(heading: string) {
  return heading.replace(/^\d+[\.\)\:\s]\s*/, '').trim()
}
</script>
