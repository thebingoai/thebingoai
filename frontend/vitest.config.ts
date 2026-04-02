import { defineConfig } from 'vitest/config'
import { resolve } from 'path'

export default defineConfig({
  test: {
    environment: 'happy-dom',
    include: ['__tests__/**/*.test.ts'],
  },
  resolve: {
    alias: {
      '~': resolve(__dirname, '.'),
      '@': resolve(__dirname, '.'),
      '#imports': resolve(__dirname, '.'),
      '#app': resolve(__dirname, '.'),
    },
  },
})
