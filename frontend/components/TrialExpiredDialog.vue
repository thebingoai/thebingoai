<template>
  <UiDialog
    :open="open"
    :closable="false"
    size="md"
  >
    <template #header>
      <h3 class="text-lg font-normal text-gray-900 w-full text-center">Account Trial Expired</h3>
    </template>
    <div class="space-y-4">
      <p class="text-center text-gray-700">
        Your trial period has ended. Thank you for trying out Bingo Enterprise!
      </p>

      <p class="text-sm text-gray-600 text-center">
        To continue using Bingo Enterprise, please upgrade your account or contact our support team.
      </p>
    </div>

    <template #footer>
      <div class="flex justify-center w-full">
        <button
          @click="handleLogout"
          class="inline-flex items-center justify-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-lg text-gray-700 bg-white hover:bg-gray-50"
        >
          Close
        </button>
      </div>
    </template>
  </UiDialog>
</template>

<script setup lang="ts">
import UiDialog from './ui/UiDialog.vue'
import { useAuthStore } from '~/stores/auth'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const authStore = useAuthStore()

const handleLogout = async () => {
  emit('update:open', false)
  await authStore.logout()
}
</script>
