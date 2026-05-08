export const useSettingsState = () => {
  const currentSection = useState<string>('settings:section', () => 'connections')
  return { currentSection }
}
