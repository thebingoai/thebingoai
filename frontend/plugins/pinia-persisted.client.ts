import { defineNuxtPlugin } from '#app'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

export default defineNuxtPlugin((nuxtApp) => {
  // @ts-ignore
  nuxtApp.$pinia.use(piniaPluginPersistedstate)
})
