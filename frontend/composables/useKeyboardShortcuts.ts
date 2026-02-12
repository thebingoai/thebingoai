export const useKeyboardShortcuts = () => {
  const router = useRouter()

  onMounted(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Cmd+K or Ctrl+K - Go to search
      if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
        event.preventDefault()
        router.push('/search')
      }

      // Cmd+N or Ctrl+N - Go to new chat
      if ((event.metaKey || event.ctrlKey) && event.key === 'n') {
        event.preventDefault()
        router.push('/chat')
      }

      // Escape - Clear current action (can be extended)
      if (event.key === 'Escape') {
        // Close modals, clear inputs, etc.
        // This can be extended with a global state for open modals
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    onUnmounted(() => {
      window.removeEventListener('keydown', handleKeyDown)
    })
  })
}
