<template>
  <Transition name="suggestion-card" appear>
    <div
      class="rounded-lg bg-white p-3"
      :class="isRecommended ? 'border border-orange-200' : 'border border-gray-100'"
    >
      <!-- Header: name + badge -->
      <div class="flex items-center justify-between mb-1.5">
        <span class="font-semibold text-gray-900 text-[13px]">
          <component :is="typeIcon" class="w-3.5 h-3.5 text-gray-400 inline-block align-middle" />
          {{ suggestion.suggested_name }}
        </span>
        <span
          class="text-[10px] rounded-full px-2 py-0.5 font-semibold"
          :class="isRecommended
            ? 'bg-green-100 text-green-800'
            : 'bg-amber-100 text-amber-800'"
        >
          {{ isRecommended ? 'Recommended' : 'Low value' }}
        </span>
      </div>

      <!-- Description -->
      <div v-if="suggestion.suggested_description" class="text-gray-500 text-xs mb-2">
        {{ suggestion.suggested_description }}
      </div>

      <!-- Reasoning -->
      <div v-if="suggestion.recommendation_reason" class="text-gray-400 text-[11px] italic mb-2.5">
        {{ suggestion.recommendation_reason }}
      </div>

      <!-- Buttons -->
      <div class="flex gap-1.5">
        <template v-if="isRecommended">
          <button
            @click="emit('accept', suggestion.id)"
            class="bg-orange-500 text-white border-none rounded-md px-3.5 py-1 text-xs cursor-pointer font-medium hover:bg-orange-600 transition-colors"
          >
            Accept
          </button>
          <button
            @click="emit('dismiss', suggestion.id)"
            class="bg-white text-gray-500 border border-gray-200 rounded-md px-3.5 py-1 text-xs cursor-pointer hover:bg-gray-50 transition-colors"
          >
            Dismiss
          </button>
        </template>
        <template v-else>
          <button
            @click="emit('accept', suggestion.id)"
            class="bg-white text-gray-500 border border-gray-200 rounded-md px-3.5 py-1 text-xs cursor-pointer hover:bg-gray-50 transition-colors"
          >
            Accept anyway
          </button>
          <button
            @click="emit('dismiss', suggestion.id)"
            class="bg-white text-gray-500 border border-gray-200 rounded-md px-3.5 py-1 text-xs cursor-pointer hover:bg-gray-50 transition-colors"
          >
            Dismiss
          </button>
        </template>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import type { SkillSuggestion } from '~/types/skillSuggestion'
import { getSkillTypeIcon } from '~/utils/skillTypeIcon'

const props = defineProps<{
  suggestion: SkillSuggestion
}>()

const emit = defineEmits<{
  accept: [id: string]
  dismiss: [id: string]
}>()

const isRecommended = computed(() => props.suggestion.recommendation === 'recommended')

const typeIcon = computed(() => getSkillTypeIcon(props.suggestion.suggested_skill_type))
</script>

<style scoped>
.suggestion-card-leave-active {
  transition: all 0.3s ease;
}
.suggestion-card-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
