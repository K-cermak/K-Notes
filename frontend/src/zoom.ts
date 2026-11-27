/**
 * The app does not zoom like a page: index.html sets maximum-scale=1, which also keeps iOS from
 * zooming in on a focused field with text under 16 px. iOS ignores it for pinching, so pinch
 * gestures are cancelled here as well. The image viewer is the exception, through allowZoom().
 */
const NO_ZOOM = /,\s*maximum-scale=1/

let allowances = 0

export function blockPageZoom(): void {
  document.addEventListener(
    'gesturestart',
    (event) => {
      // A page already zoomed in, for example after the image viewer closed, can still zoom out.
      if (allowances === 0 && (window.visualViewport?.scale ?? 1) <= 1) event.preventDefault()
    },
    { passive: false },
  )
}

/** Lets the page be zoomed until the returned function is called. */
export function allowZoom(): () => void {
  allowances += 1
  setViewport(false)
  let released = false
  return () => {
    if (released) return
    released = true
    allowances -= 1
    if (allowances === 0) setViewport(true)
  }
}

function setViewport(limited: boolean): void {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="viewport"]')
  if (!meta) return
  const content = meta.content.replace(NO_ZOOM, '')
  meta.content = limited ? `${content}, maximum-scale=1` : content
}
