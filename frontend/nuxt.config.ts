// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ssr: false,
  nitro: {
    preset: 'static',
  },
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },

  modules: [
    '@nuxtjs/tailwindcss',
    '@pinia/nuxt',
    '@vueuse/nuxt',
    '@nuxtjs/google-fonts'
  ],

  components: [
    {
      path: '~/components',
      pathPrefix: false
    }
  ],

  css: [
    'gridstack/dist/gridstack.css',
    '~/assets/css/main.css',
  ],

  googleFonts: {
    families: {
      'DM Sans': [200, 300, 400, 500, 600, 700],
      'JetBrains Mono': [400, 500, 600]
    },
    display: 'swap',
    download: true
  },

  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
      chatFileMaxSizeMb: Number(process.env.NUXT_PUBLIC_CHAT_FILE_MAX_SIZE_MB) || 50,
    }
  },

  routeRules: {
    // Upload routes need longer timeout — server-side processing (type inference,
    // SQLite creation) can take 10-30s for large files after upload completes.
    '/api/connections/upload-dataset': {
      proxy: {
        to: `${process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000'}/api/connections/upload-dataset`,
        timeout: 120_000,
        headers: {
          'X-Forwarded-Host': 'localhost:3000'
        }
      }
    },
    '/api/connections/upload-sqlite': {
      proxy: {
        to: `${process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000'}/api/connections/upload-sqlite`,
        timeout: 120_000,
        headers: {
          'X-Forwarded-Host': 'localhost:3000'
        }
      }
    },
    // CSV/Excel uploads go through /api/connections/upload-dataset instead.
    // This route handles non-dataset file uploads (images, PDF, DOCX).
    '/api/chat/files/upload': {
      proxy: {
        to: `${process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000'}/api/chat/files/upload`,
        timeout: 120_000,
        headers: {
          'X-Forwarded-Host': 'localhost:3000'
        }
      }
    },
    '/api/**': {
      proxy: {
        // In Docker: BACKEND_INTERNAL_URL=http://backend:8000 (set in docker-compose)
        // Native dev: falls back to http://localhost:8000
        to: `${process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000'}/api/**`,
        headers: {
          'X-Forwarded-Host': 'localhost:3000'
        }
      }
    },
    // SSO proxy — routes /sso-api/** to the SSO service
    '/sso-api/**': {
      proxy: {
        to: `${process.env.NUXT_PUBLIC_SSO_BASE_URL || 'https://sso.thelead.io'}/api/v1/**`
      }
    }
  },

  vite: {
    optimizeDeps: {
      include: ['sql.js'],
      exclude: [],
    },
  },

  typescript: {
    strict: false,
    typeCheck: false
  },

  app: {
    pageTransition: { name: 'page-fade-slide', mode: 'out-in' },
    head: {
      title: 'TheBingo.ai',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'RAG system for indexing and querying markdown files' }
      ],
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }
      ]
    }
  }
})
