// middleware/admin.ts
export default defineNuxtRouteMiddleware(() => {
  const authStore = useAuthStore()
  if (!authStore.user || authStore.user.role !== 'admin') {
    return navigateTo('/chat')
  }
})
