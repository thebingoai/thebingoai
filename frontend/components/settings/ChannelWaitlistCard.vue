<template>
  <UiCard class="relative overflow-hidden px-4 py-5 h-56 w-56 max-md:w-full">
    <!-- Status strip -->
    <div
      class="absolute top-0 left-0 right-0 h-[3px]"
      :class="status === 'available' ? 'bg-green-400' : 'bg-gray-200 dark:bg-neutral-600'"
    />

    <div class="flex flex-col h-full">
      <!-- Header: icon + name + status badge -->
      <div class="flex items-start gap-2.5">
        <div class="h-8 w-8 shrink-0 rounded-full flex items-center justify-center" :class="iconBg">
          <slot name="icon" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5 flex-wrap">
            <p class="text-sm font-semibold text-gray-900 dark:text-neutral-100">{{ name }}</p>
            <span
              class="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium"
              :class="statusBadgeClass"
            >
              {{ statusLabel }}
            </span>
          </div>
        </div>
      </div>

      <!-- Body: description -->
      <p class="mt-3 text-xs text-gray-500 dark:text-neutral-400 flex-1 leading-relaxed">{{ description }}</p>

      <!-- Footer: CTA -->
      <div class="mt-3 pt-3 border-t border-gray-100 dark:border-neutral-700">
        <a
          :href="`mailto:${mailtoAddress}?subject=${encodeURIComponent(mailtoSubject)}`"
          class="inline-flex items-center justify-center gap-1.5 w-full text-xs font-medium px-3 py-2 rounded-lg transition-colors"
          :class="status === 'available'
            ? 'bg-gray-900 dark:bg-neutral-100 text-white dark:text-neutral-900 hover:bg-gray-700 dark:hover:bg-neutral-200'
            : 'border border-gray-200 dark:border-neutral-600 text-gray-600 dark:text-neutral-300 hover:bg-gray-50 dark:hover:bg-neutral-800'"
        >
          {{ buttonLabel }}
        </a>
      </div>
    </div>
  </UiCard>
</template>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  name: string
  description: string
  mailtoAddress?: string
  mailtoSubject: string
  status?: 'available' | 'waitlist' | 'coming_soon'
  iconBg?: string
}>(), {
  mailtoAddress: 'hello@thebingo.ai',
  status: 'available',
  iconBg: 'bg-gray-100 dark:bg-neutral-700 text-gray-500',
})

const statusLabel = computed(() => {
  if (props.status === 'available') return 'available'
  if (props.status === 'waitlist') return 'waitlist'
  return 'coming soon'
})

const statusBadgeClass = computed(() => {
  if (props.status === 'available') return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
  return 'bg-gray-100 dark:bg-neutral-700 text-gray-500 dark:text-neutral-400'
})

const buttonLabel = computed(() =>
  props.status === 'available' ? 'Connect' : 'Join waitlist'
)
</script>
