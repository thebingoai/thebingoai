<template>
  <div v-if="suggestions.length > 0" class="border-b border-gray-100">
    <!-- Header -->
    <button
      @click="chatStore.toggleInfoSection('skills')"
      class="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
    >
      <div class="flex items-center gap-1.5">
        <span class="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Suggested Skills</span>
        <span class="text-[10px] bg-orange-50 text-orange-600 px-1.5 py-px rounded-full font-semibold">
          {{ suggestions.length }}
        </span>
      </div>
      <svg
        class="w-3 h-3 text-gray-300 transition-transform duration-200"
        :class="{ 'rotate-180': chatStore.infoPanelSections.skills }"
        fill="none" viewBox="0 0 24 24" stroke="currentColor"
      >
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Content -->
    <div v-show="chatStore.infoPanelSections.skills" class="px-4 pb-3">
      <TransitionGroup name="skill-row" tag="div">
        <div v-for="s in suggestions" :key="s.id">
          <!-- Compact row -->
          <div
            class="flex items-center justify-between py-2 border-b border-gray-50 last:border-b-0"
          >
            <button
              @click="toggleExpanded(s.id)"
              class="flex items-center gap-2 min-w-0 flex-1 text-left"
            >
              <component :is="getSkillTypeIcon(s.suggested_skill_type)" class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <div class="min-w-0">
                <div class="text-[11px] font-semibold text-gray-900 truncate">{{ s.suggested_name }}</div>
                <div class="text-[10px] text-gray-400">
                  {{ s.frequency_count ? `Detected ${s.frequency_count} times` : 'Detected' }}
                </div>
              </div>
            </button>
            <div class="flex items-center gap-1 flex-shrink-0 ml-2">
              <button
                @click="handleAccept(s.id)"
                class="text-[9px] rounded-lg px-1.5 py-0.5 transition-colors"
                :class="s.recommendation === 'recommended'
                  ? 'bg-green-100 text-green-800 hover:bg-green-200'
                  : 'border border-gray-200 text-gray-300 hover:text-gray-500 hover:border-gray-300'"
              >
                &#10003;
              </button>
              <button
                @click="handleDismiss(s.id)"
                class="text-[9px] rounded-lg px-1.5 py-0.5 border border-gray-200 text-gray-300 hover:text-gray-500 hover:border-gray-300 transition-colors"
              >
                &#10005;
              </button>
            </div>
          </div>

          <!-- Expanded details -->
          <div v-if="expandedIds.has(s.id)" class="bg-gray-50 rounded-md p-2 mt-1.5 mb-2">
            <p v-if="s.suggested_description" class="text-[11px] text-gray-600 mb-1">{{ s.suggested_description }}</p>
            <p v-if="s.recommendation_reason" class="text-[10px] text-gray-400 italic">{{ s.recommendation_reason }}</p>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<script setup lang="ts">
import { getSkillTypeIcon } from '~/utils/skillTypeIcon'

const chatStore = useChatStore()
const api = useApi()

const suggestions = computed(() => chatStore.pendingSkillSuggestions)

const expandedIds = ref(new Set<string>())

const toggleExpanded = (id: string) => {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}

const handleAccept = async (id: string) => {
  try {
    await api.skills.respondToSuggestion(id, 'accept')
  } catch { /* best-effort */ }
  chatStore.removeSkillSuggestion(id)
}

const handleDismiss = async (id: string) => {
  try {
    await api.skills.respondToSuggestion(id, 'dismiss')
  } catch { /* best-effort */ }
  chatStore.removeSkillSuggestion(id)
}
</script>

<style scoped>
.skill-row-leave-active {
  transition: all 0.3s ease;
}
.skill-row-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
.skill-row-move {
  transition: transform 0.3s ease;
}
</style>
