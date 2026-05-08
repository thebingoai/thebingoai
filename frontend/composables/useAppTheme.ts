// Paper-theme switcher (kraft / cool / ink) for the Settings surface.
// Layers on top of useColorMode (which only handles light/dark).
// Persisted in localStorage; applied as `theme-{name}` class on <html>.

export type AppTheme = 'kraft' | 'cool' | 'ink'

const THEMES: AppTheme[] = ['kraft', 'cool', 'ink']
const STORAGE_KEY = 'bingo-app-theme'

const isAppTheme = (v: unknown): v is AppTheme =>
  typeof v === 'string' && (THEMES as string[]).includes(v)

export const useAppTheme = () => {
  const preference = useState<AppTheme>('app-theme', () => {
    if (import.meta.client) {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (isAppTheme(stored)) return stored
    }
    return 'kraft'
  })

  const apply = (theme: AppTheme) => {
    if (!import.meta.client) return
    const cl = document.documentElement.classList
    THEMES.forEach(t => cl.remove(`theme-${t}`))
    cl.add(`theme-${theme}`)
  }

  if (import.meta.client) {
    apply(preference.value)
    watch(preference, val => {
      localStorage.setItem(STORAGE_KEY, val)
      apply(val)
    })
  }

  return { preference, themes: THEMES }
}
