<template>
  <div class="rounded-lg border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
    <h2 class="mb-4 text-lg font-semibold text-neutral-900 dark:text-neutral-100">
      Recent Activity
    </h2>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 3" :key="i" class="flex items-start gap-3">
        <UiSkeleton width="40px" height="40px" circle />
        <div class="flex-1">
          <UiSkeleton width="60%" height="16px" class="mb-2" />
          <UiSkeleton width="40%" height="14px" />
        </div>
      </div>
    </div>

    <div v-else-if="activities.length === 0">
      <UiEmptyState
        title="No recent activity"
        description="Activity will appear here as you use the system"
      />
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="activity in activities"
        :key="activity.id"
        class="flex items-start gap-3"
      >
        <div class="rounded-full p-2" :class="getActivityIconBg(activity.type)">
          <component :is="getActivityIcon(activity.type)" class="h-5 w-5" :class="getActivityIconColor(activity.type)" />
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm text-neutral-900 dark:text-neutral-100">
            {{ activity.description }}
          </p>
          <p class="mt-0.5 text-xs text-neutral-500 dark:text-neutral-400">
            {{ timeAgo(activity.timestamp) }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Upload, MessageSquare, AlertCircle, CheckCircle } from 'lucide-vue-next'
import type { Activity } from '~/types'
import { timeAgo } from '~/utils/format'

interface Props {
  activities: Activity[]
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false
})

const getActivityIcon = (type: Activity['type']) => {
  const icons = {
    upload: Upload,
    upload_complete: CheckCircle,
    chat: MessageSquare,
    error: AlertCircle
  }
  return icons[type] || Upload
}

const getActivityIconBg = (type: Activity['type']) => {
  const classes = {
    upload: 'bg-brand-100 dark:bg-brand-900/20',
    upload_complete: 'bg-success-100 dark:bg-success-900/20',
    chat: 'bg-info-100 dark:bg-info-900/20',
    error: 'bg-error-100 dark:bg-error-900/20'
  }
  return classes[type] || classes.upload
}

const getActivityIconColor = (type: Activity['type']) => {
  const classes = {
    upload: 'text-brand-600 dark:text-brand-400',
    upload_complete: 'text-success-600 dark:text-success-400',
    chat: 'text-info-600 dark:text-info-400',
    error: 'text-error-600 dark:text-error-400'
  }
  return classes[type] || classes.upload
}
</script>
