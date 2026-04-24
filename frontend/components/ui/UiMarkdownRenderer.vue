<template>
  <div class="prose-chat" v-html="renderedMarkdown" />
</template>

<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import { useShikiHighlighter } from '~/composables/useShikiHighlighter'

interface Props {
  content: string
}

const props = defineProps<Props>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true
})

const highlighter = ref<any>(null)

onMounted(async () => {
  try {
    highlighter.value = await useShikiHighlighter()

    // Override code block rendering with syntax highlighting
    const defaultRender = md.renderer.rules.fence || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))

    md.renderer.rules.fence = (tokens, idx, options, env, self) => {
      const token = tokens[idx]
      const code = token.content
      const lang = token.info || 'text'

      if (highlighter.value && lang) {
        try {
          const colorMode = useColorMode()
          const theme = colorMode.value === 'dark' ? 'github-dark' : 'github-light'
          const html = highlighter.value.codeToHtml(code, { lang, theme })
          return `<div class="shiki-wrapper">${html}</div>`
        } catch (e) {
          // Fallback to default rendering if highlighting fails
        }
      }

      return defaultRender(tokens, idx, options, env, self)
    }
  } catch (error) {
    console.warn('Failed to load syntax highlighter:', error)
  }
})

const renderedMarkdown = computed(() => {
  try {
    return md.render(props.content)
  } catch (error) {
    console.error('Failed to render markdown:', error)
    return `<p class="text-error-600">Failed to render markdown</p>`
  }
})
</script>

<style>
.shiki-wrapper {
  @apply my-3 overflow-x-auto rounded-lg;
}

.shiki-wrapper pre {
  @apply m-0 p-4;
}
</style>
