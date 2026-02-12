export const useDropzone = () => {
  const isDragging = ref(false)
  const dragCounter = ref(0)

  const onDragEnter = (event: DragEvent) => {
    event.preventDefault()
    dragCounter.value++
    if (dragCounter.value === 1) {
      isDragging.value = true
    }
  }

  const onDragLeave = (event: DragEvent) => {
    event.preventDefault()
    dragCounter.value--
    if (dragCounter.value === 0) {
      isDragging.value = false
    }
  }

  const onDragOver = (event: DragEvent) => {
    event.preventDefault()
  }

  const onDrop = (event: DragEvent, callback: (files: File[]) => void) => {
    event.preventDefault()
    isDragging.value = false
    dragCounter.value = 0

    const files = Array.from(event.dataTransfer?.files || [])
    if (files.length > 0) {
      callback(files)
    }
  }

  const reset = () => {
    isDragging.value = false
    dragCounter.value = 0
  }

  return {
    isDragging: readonly(isDragging),
    onDragEnter,
    onDragLeave,
    onDragOver,
    onDrop,
    reset
  }
}
