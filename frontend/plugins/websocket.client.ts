/**
 * WebSocket auto-connect plugin.
 * Watches auth state and connects/disconnects the persistent WebSocket accordingly.
 */
export default defineNuxtPlugin(() => {
  const authStore = useAuthStore()
  const ws = useWebSocket()

  // Connect immediately if already authenticated (e.g. page refresh with stored token)
  if (authStore.isAuthenticated && authStore.token) {
    ws.connect(authStore.token)
  }

  // Watch for login / logout
  watch(
    () => authStore.isAuthenticated,
    (isAuth) => {
      if (isAuth && authStore.token) {
        ws.connect(authStore.token)
      } else {
        ws.disconnect()
      }
    }
  )
})
