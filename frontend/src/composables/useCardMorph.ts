import { onBeforeUnmount, ref } from 'vue'

/** The note whose card is hidden while the editor stands in for it (SPEC 9, Editor). */
export const hiddenCard = ref<string | null>(null)

type Phase = 'none' | 'waiting' | 'growing' | 'shrinking'

function reducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** The masonry cell of a note's card; a card fading out of a section it left does not count. */
function cardOf(id: string): HTMLElement | null {
  const cells = document.querySelectorAll<HTMLElement>(`[data-masonry-key="${CSS.escape(id)}"]`)
  return [...cells].find((cell) => !cell.classList.contains('card-leave')) ?? null
}

function cardRect(id: string): DOMRect | null {
  const rect = cardOf(id)?.getBoundingClientRect()
  if (!rect || rect.width === 0) return null
  const onScreen =
    rect.bottom > 0 &&
    rect.top < window.innerHeight &&
    rect.right > 0 &&
    rect.left < window.innerWidth
  return onScreen ? rect : null
}

/** The transform that lays a box drawn at `to` over `from`, with the origin at its top left. */
function between(from: DOMRect, to: DOMRect): string {
  const x = from.left - to.left
  const y = from.top - to.top
  return `translate(${x}px, ${y}px) scale(${from.width / to.width}, ${from.height / to.height})`
}

// Read from the tokens, so the CSS animations that run alongside (the scrim, the closing hold) last
// exactly as long.
function timing(direction: 'in' | 'out'): { duration: number; easing: string } {
  const style = getComputedStyle(document.documentElement)
  return {
    duration:
      parseFloat(style.getPropertyValue(`--motion-travel-${direction}`)) ||
      (direction === 'in' ? 240 : 200),
    easing: style.getPropertyValue('--motion-travel-ease').trim() || 'ease-in-out',
  }
}

/**
 * Grows the editor out of the note's card and shrinks it back into it. The box is scaled with a
 * transform, which would stretch the text, so its content fades in once the box is most of the way
 * there and out at the start of the shrink; the box carries the note's colour meanwhile.
 */
export function useCardMorph() {
  const phase = ref<Phase>('none')
  let running: Animation[] = []

  function stop(): void {
    for (const animation of running) animation.cancel()
    running = []
  }

  function animate(
    box: HTMLElement,
    from: string,
    to: string,
    fade: Keyframe[],
    fill: FillMode,
    direction: 'in' | 'out',
  ) {
    const { duration, easing } = timing(direction)
    const origin = { transformOrigin: '0 0' }
    running = [
      box.animate(
        [
          { ...origin, transform: from },
          { ...origin, transform: to },
        ],
        {
          duration,
          easing,
          fill,
        },
      ),
      ...[...box.children].map((child) => child.animate(fade, { duration, fill })),
    ]
    return running[0]!
  }

  /** As a note opens: it grows out of its card if the card is on screen, otherwise opens plainly. */
  function prepare(id: string): void {
    stop()
    hiddenCard.value = null
    phase.value = !reducedMotion() && cardRect(id) ? 'waiting' : 'none'
  }

  /**
   * Starts the growth once the editor shows the note, so the box grows to its real size. The
   * editor stays transparent until then.
   */
  function grow(box: HTMLElement | null, id: string): void {
    if (phase.value !== 'waiting') return
    const from = box && cardRect(id)
    if (!box || !from) {
      phase.value = 'none'
      return
    }
    phase.value = 'growing'
    hiddenCard.value = id
    // The box is past half of the way at a quarter of the time, so the content can start to show
    // then without looking stretched.
    const fade = [
      { opacity: 0 },
      { opacity: 0, offset: 0.25 },
      { opacity: 1, offset: 0.6 },
      { opacity: 1 },
    ]
    animate(box, between(from, box.getBoundingClientRect()), 'none', fade, 'none', 'in')
  }

  /**
   * As the editor closes: shrinks it into the card and returns true, or returns false when there is
   * no card on screen to go to and the editor should leave with its own animation.
   */
  function shrink(box: HTMLElement | null, id: string): boolean {
    stop()
    const to = !reducedMotion() && box ? cardRect(id) : null
    if (!box || !to) {
      phase.value = 'none'
      hiddenCard.value = null
      return false
    }
    phase.value = 'shrinking'
    hiddenCard.value = id
    // Gone before the box is halfway, while the squeeze is not yet plain on the text.
    const fade = [{ opacity: 1 }, { opacity: 0, offset: 0.18 }, { opacity: 0 }]
    const animation = animate(
      box,
      'none',
      between(to, box.getBoundingClientRect()),
      fade,
      'forwards',
      'out',
    )
    animation.finished.then(
      () => {
        if (hiddenCard.value === id) hiddenCard.value = null
      },
      // Cancelled by the next note opening, which shows the card itself.
      () => {},
    )
    return true
  }

  onBeforeUnmount(() => {
    stop()
    hiddenCard.value = null
  })

  return { phase, prepare, grow, shrink }
}
