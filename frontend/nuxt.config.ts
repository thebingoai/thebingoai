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
      supabaseUrl: process.env.NUXT_PUBLIC_SUPABASE_URL || '',
      supabaseAnonKey: process.env.NUXT_PUBLIC_SUPABASE_ANON_KEY || '',
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
    // SSO proxy (used when AUTH_PROVIDER=sso in enterprise)
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
