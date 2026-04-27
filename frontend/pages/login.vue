<template>
  <div class="min-h-screen flex">
    <!-- Left panel: editorial/branding (hidden on mobile) -->
    <div class="hidden lg:flex lg:w-[42%] flex-col justify-between bg-[#FAF5ED] dark:bg-neutral-950 border-r border-neutral-200 dark:border-neutral-800 p-10">
      <!-- Logo -->
      <div>
        <span class="text-xl font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
          bingo<span class="text-purple-600">.</span>
        </span>
      </div>

      <!-- Marketing headline -->
      <div class="flex flex-col justify-center">
        <p class="text-[11px] tracking-widest font-medium text-neutral-500 dark:text-neutral-500 uppercase mb-5">
          Sign In
        </p>
        <h1 class="font-display text-5xl font-bold leading-[1.1] text-neutral-900 dark:text-neutral-50 mb-6">
          The assistant<br>
          that <em class="italic text-purple-600">queries</em> with<br>
          you.
        </h1>
        <p class="text-sm text-neutral-500 dark:text-neutral-400 leading-relaxed max-w-xs">
          Plug in a warehouse, ask a question, read a briefing over coffee. Your data, annotated.
        </p>

        <!-- Decorative progress stepper -->
        <div class="mt-10 border-t border-dashed border-neutral-300 dark:border-neutral-700 pt-6">
          <p class="text-[11px] tracking-widest font-medium text-neutral-500 dark:text-neutral-500 uppercase mb-4">
            Setup · 1/4
          </p>
          <div class="flex gap-1.5 mb-3">
            <div class="h-0.5 flex-1 bg-purple-600 rounded-full"></div>
            <div class="h-0.5 flex-1 bg-neutral-200 dark:bg-neutral-700 rounded-full"></div>
            <div class="h-0.5 flex-1 bg-neutral-200 dark:bg-neutral-700 rounded-full"></div>
            <div class="h-0.5 flex-1 bg-neutral-200 dark:bg-neutral-700 rounded-full"></div>
          </div>
          <div class="flex justify-between text-[11px] text-neutral-400 dark:text-neutral-600">
            <span>Account</span><span>Workspace</span><span>Connect</span><span>First task</span>
          </div>
        </div>
      </div>

      <!-- Compliance footer -->
      <div>
        <p class="text-[11px] text-neutral-400 dark:text-neutral-600 tracking-wide">SOC 2 Type II · GDPR · HIPAA</p>
        <p class="text-[11px] text-neutral-400 dark:text-neutral-600 mt-1">Your queries never leave your warehouse.</p>
      </div>
    </div>

    <!-- Right panel: auth form -->
    <div class="flex-1 flex flex-col items-center justify-center bg-white dark:bg-neutral-900 px-8 py-12">
      <div class="w-full max-w-md">
        <h2 class="font-display text-5xl font-bold text-neutral-900 dark:text-neutral-50 mb-1">Welcome back.</h2>
        <p class="text-sm text-neutral-500 dark:text-neutral-400 mb-8">
          Sign in to <span class="font-mono text-xs">{{ config.public.workspaceName }}</span>
        </p>

        <div v-if="error" class="mb-6 p-3 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-600 dark:text-red-400">
          {{ error }}
        </div>

        <!-- Google OAuth -->
        <template v-if="authStore.hasGoogleOAuth">
          <button
            type="button"
            :disabled="loading"
            class="w-full h-11 flex items-center justify-center gap-3 border border-neutral-300 dark:border-neutral-700 rounded-lg text-sm font-medium text-neutral-700 dark:text-neutral-200 hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mb-5"
            @click="handleGoogleLogin"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" fill="#4285F4"/>
              <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" fill="#34A853"/>
              <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z" fill="#FBBC05"/>
              <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z" fill="#EA4335"/>
            </svg>
            Continue with Google
          </button>

          <div class="relative mb-5">
            <div class="absolute inset-0 flex items-center">
              <div class="w-full border-t border-neutral-200 dark:border-neutral-700"></div>
            </div>
            <div class="relative flex justify-center">
              <span class="px-3 bg-white dark:bg-neutral-900 text-[11px] tracking-widest uppercase text-neutral-400">
                or email
              </span>
            </div>
          </div>
        </template>

        <!-- Email / Password form -->
        <form @submit.prevent="handleLogin" class="space-y-4">
          <UiInput
            v-model="email"
            type="email"
            label="WORK EMAIL"
            placeholder="you@company.com"
            required
          />

          <!-- Password with visibility toggle -->
          <div class="relative">
            <UiInput
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              label="PASSWORD"
              placeholder="••••••••"
              required
            />
            <button
              type="button"
              :aria-label="showPassword ? 'Hide password' : 'Show password'"
              class="absolute right-3 top-[34px] text-neutral-400 hover:text-neutral-600 dark:text-neutral-500 dark:hover:text-neutral-300 transition-colors"
              @click="showPassword = !showPassword"
            >
              <EyeOff v-if="showPassword" class="h-4 w-4" />
              <Eye v-else class="h-4 w-4" />
            </button>
          </div>

          <!-- Remember me + Forgot password -->
          <div class="flex items-center justify-between text-sm">
            <label class="flex items-center gap-2 text-neutral-600 dark:text-neutral-400 cursor-pointer select-none">
              <input
                v-model="remember"
                type="checkbox"
                class="rounded border-neutral-300 dark:border-neutral-600 text-purple-600 focus:ring-purple-500 dark:bg-neutral-800"
              />
              <span>Remember me on this device</span>
            </label>
            <NuxtLink
              to="/auth/forgot-password"
              class="text-purple-600 hover:text-purple-700 dark:text-purple-400 dark:hover:text-purple-300"
            >
              Forgot password?
            </NuxtLink>
          </div>

          <!-- Purple Sign In button -->
          <button
            type="submit"
            :disabled="loading"
            class="w-full h-11 bg-purple-700 hover:bg-purple-800 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Loader2 v-if="loading" class="h-4 w-4 animate-spin" />
            <span v-else>Sign in</span>
          </button>
        </form>

        <p class="mt-6 text-center text-sm text-neutral-500 dark:text-neutral-400">
          No account?
          <NuxtLink to="/register" class="text-purple-600 hover:text-purple-700 dark:text-purple-400 hover:underline">
            Start free trial
          </NuxtLink>
        </p>
      </div>
    </div>

    <TrialExpiredDialog v-model:open="showTrialExpired" />
  </div>
</template>

<script setup lang="ts">
import { Loader2, Eye, EyeOff } from 'lucide-vue-next'
import TrialExpiredDialog from '~/components/TrialExpiredDialog.vue'

const config = useRuntimeConfig()
const authStore = useAuthStore()
const router = useRouter()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const remember = ref(false)
const loading = computed(() => authStore.loading)
const error = computed(() => authStore.error)
const showTrialExpired = ref(false)

async function handleLogin() {
  const result = await authStore.login({ email: email.value, password: password.value })

  if (authStore.isAccountInactive) {
    showTrialExpired.value = true
  } else if (result.success) {
    router.push('/chat')
  }
}

function handleGoogleLogin() {
  authStore.loginWithGoogle()
}

definePageMeta({
  layout: false
})
</script>
