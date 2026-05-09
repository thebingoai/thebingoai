<template>
  <div class="min-h-screen flex">
    <!-- Left panel -->
    <AuthBrandingPanel :step="3" step-context="First Task" />

    <!-- Right panel -->
    <div class="flex-1 h-screen flex flex-col bg-white dark:bg-neutral-900 overflow-y-auto">
      <div class="flex-1 px-10 py-12 max-w-2xl mx-auto w-full">

        <!-- Header -->
        <h2 class="font-display text-4xl font-bold text-neutral-900 dark:text-neutral-50 mb-2">
          Ask Bingo your <em class="italic text-purple-600">first question.</em>
        </h2>
        <p class="text-sm text-neutral-500 dark:text-neutral-400 mb-8 max-w-lg">
          Type anything, or pick a starter we've tailored to your schema.
        </p>

        <!-- Question textarea -->
        <div class="mb-4">
          <textarea
            v-model="question"
            rows="4"
            placeholder="Which enterprise accounts are at risk of churning this quarter?"
            class="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 dark:placeholder:text-neutral-500 text-sm leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-shadow"
          />
        </div>

        <!-- Schema context + Send button row -->
        <div class="flex items-center justify-between mb-8">
          <div v-if="recentConnection" class="flex items-center gap-2 text-xs text-neutral-400 dark:text-neutral-500">
            <svg class="h-3.5 w-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <ellipse cx="12" cy="5" rx="9" ry="3"/>
              <path d="M3 5v14c0 1.657 4.03 3 9 3s9-1.343 9-3V5"/>
              <path d="M3 12c0 1.657 4.03 3 9 3s9-1.343 9-3"/>
            </svg>
            <span class="font-medium text-neutral-500 dark:text-neutral-400">{{ recentConnection.name }}</span>
            <template v-if="recentConnection.table_count != null">
              <span>·</span>
              <span>{{ recentConnection.table_count }} tables</span>
            </template>
          </div>
          <div v-else class="flex-1" />

          <button
            class="flex items-center gap-2 bg-purple-700 hover:bg-purple-800 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="!question.trim()"
            @click="handleSend"
          >
            <span>Send</span>
            <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z"/>
            </svg>
          </button>
        </div>

        <!-- Starters section -->
        <div>
          <p class="text-sm tracking-widest font-medium text-neutral-400 dark:text-neutral-500 uppercase mb-3">
            Starters — Tailored to your schema
          </p>

          <div class="grid grid-cols-2 gap-3">
            <button
              v-for="starter in starters"
              :key="starter.title"
              class="flex flex-col gap-1.5 p-4 rounded-xl border text-left transition-all focus:outline-none"
              :class="question === starter.question
                ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/40 ring-1 ring-purple-500'
                : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600 hover:bg-neutral-50 dark:hover:bg-neutral-800/50'"
              @click="question = starter.question"
            >
              <p class="text-sm font-semibold text-neutral-800 dark:text-neutral-100 leading-tight">{{ starter.title }}</p>
              <p class="text-xs text-neutral-400 dark:text-neutral-500 leading-relaxed">{{ starter.description }}</p>
            </button>
          </div>
        </div>

      </div>

      <!-- Bottom action bar -->
      <div class="sticky bottom-0 border-t border-neutral-200 dark:border-neutral-800 px-10 py-4 flex items-center justify-between bg-white dark:bg-neutral-900">
        <button
          class="text-sm text-neutral-500 dark:text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200 transition-colors"
          @click="navigateTo('/connect')"
        >
          Back
        </button>

        <button
          class="flex items-center gap-2 bg-purple-700 hover:bg-purple-800 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
          @click="handleFinish"
        >
          <span>Finish &amp; open workbench</span>
          <span>›</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface DatabaseConnection {
  id: number
  name: string
  db_type: string
  table_count: number | null
  source_filename: string | null
  is_ephemeral: boolean
  profiling_status: string | null
}

interface Starter {
  title: string
  description: string
  question: string
}

const starters: Starter[] = [
  {
    title: 'Describe the shape of my data',
    description: 'A high-level view of every table, its size, and how they relate.',
    question: 'Give me a high-level overview of every table in my database — its size, key columns, and how the tables relate to each other.',
  },
  {
    title: 'Weekly revenue snapshot',
    description: 'A repeatable report of MRR, ARR, churn, and top 3 workdays.',
    question: 'Generate a weekly revenue snapshot showing MRR, ARR, churn rate, and the top 3 highest-revenue workdays this month.',
  },
  {
    title: 'Find my at-risk customers',
    description: 'Usage insight + open issues + renewal window.',
    question: 'Which customers are at risk of churning this quarter? Consider usage trends, open support issues, and upcoming renewal dates.',
  },
  {
    title: 'Onboarding funnel',
    description: 'Step-by-step conversion rate with cohort slicing.',
    question: 'Show me the onboarding funnel with step-by-step conversion rates, broken down by acquisition cohort.',
  },
]

const api = useApi()
const chatStore = useChatStore()

const question = ref('')
const recentConnection = ref<DatabaseConnection | null>(null)

function handleSend() {
  if (!question.value.trim()) return
  chatStore.inputText = question.value
  navigateTo('/chat')
}

function handleFinish() {
  chatStore.inputText = question.value
  navigateTo('/chat')
}

onMounted(async () => {
  try {
    const conns: DatabaseConnection[] = await api.connections.list()
    const nonEphemeral = conns.filter((c: DatabaseConnection) => !c.is_ephemeral)
    if (nonEphemeral.length > 0) {
      recentConnection.value = nonEphemeral[nonEphemeral.length - 1]
    }
  } catch {
    // Connection fetch is informational only — page works without it
  }
})

definePageMeta({
  layout: false,
  middleware: 'auth',
  pageTransition: false,
  layoutTransition: false,
})
</script>
