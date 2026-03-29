import { getHighlighter } from 'shiki'

let highlighterPromise: Promise<any> | null = null

export function useShikiHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = getHighlighter({
      themes: ['github-dark', 'github-light'],
      langs: ['javascript', 'typescript', 'python', 'bash', 'json', 'markdown', 'html', 'css', 'sql'],
    })
  }
  return highlighterPromise
}
