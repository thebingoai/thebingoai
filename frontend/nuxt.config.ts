// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  ssr: false,
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
      ssoBaseUrl: 'https://sso.thelead.io',  // overridable via NUXT_PUBLIC_SSO_BASE_URL at runtime
    }
  },

  routeRules: {
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
    '/sso-api/**': {
      proxy: {
        to: 'https://sso.thelead.io/api/v1/**'
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
    head: {
      title: 'LLM-MD-CLI',
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
