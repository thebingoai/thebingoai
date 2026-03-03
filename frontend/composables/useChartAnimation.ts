import type { Ref } from 'vue'
import type { ChartAnimationConfig, EntranceAnimation } from '~/types/chart'

export function useChartAnimation(
  containerRef: Ref<HTMLElement | null>,
  animationConfig?: ChartAnimationConfig
) {
  const entrance: EntranceAnimation = animationConfig?.entrance ?? 'fadeIn'
  const duration = animationConfig?.entranceDuration ?? 600
  const delay = animationConfig?.entranceDelay ?? 0

  async function playEntranceAnimation() {
    const el = containerRef.value
    if (!el || entrance === 'none') return

    // Dynamically import anime to avoid SSR issues
    const anime = (await import('animejs')).default

    const baseParams = {
      targets: el,
      duration,
      delay,
      easing: 'easeOutCubic',
    }

    if (entrance === 'fadeIn') {
      // Set initial state
      el.style.opacity = '0'
      anime({ ...baseParams, opacity: [0, 1] })
    } else if (entrance === 'slideUp') {
      el.style.opacity = '0'
      el.style.transform = 'translateY(20px)'
      anime({ ...baseParams, opacity: [0, 1], translateY: [20, 0] })
    } else if (entrance === 'grow') {
      el.style.opacity = '0'
      el.style.transform = 'scale(0.95)'
      anime({ ...baseParams, opacity: [0, 1], scale: [0.95, 1] })
    }
  }

  onMounted(() => {
    playEntranceAnimation()
  })
}
