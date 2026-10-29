import type maplibregl from 'maplibre-gl'
import { type RefObject, useCallback, useEffect, useState } from 'react'

// Same breakpoint as Tailwind's `lg`: below it the map sits under the cards
// and can be enlarged; from it the map already fills its side of the window.
const NARROW_QUERY = '(max-width: 1023px)'

/**
 * Full-screen map on phones. Entering adds a history entry, so the browser's
 * back gesture leaves full screen instead of the page; Esc leaves it too.
 * While full screen the page behind doesn't scroll and the map takes one-finger
 * gestures (no page to scroll past). Returns whether it is on and a toggle.
 */
export default function useFullscreenMap(
  mapRef: RefObject<maplibregl.Map | null>,
): [boolean, () => void] {
  const [full, setFull] = useState(false)

  // Back / forward through our history entry turns full screen off / on.
  useEffect(() => {
    const onPopState = () => setFull(Boolean(window.history.state?.fullMap))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const exit = useCallback(() => {
    if (window.history.state?.fullMap) {
      window.history.back() // popstate then turns it off
    } else {
      setFull(false)
    }
  }, [])

  const toggle = useCallback(() => {
    if (full) {
      exit()
      return
    }
    window.history.pushState({ ...window.history.state, fullMap: true }, '')
    setFull(true)
  }, [full, exit])

  useEffect(() => {
    const map = mapRef.current
    // The container just changed size; MapLibre redraws for the new one.
    map?.resize()
    if (!full) {
      return
    }
    const gestures = map?.cooperativeGestures
    const cooperative = gestures?.isEnabled()
    gestures?.disable()
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        exit()
      }
    }
    // Turning a tablet to a wide layout: back to the side-by-side map.
    const narrow = window.matchMedia(NARROW_QUERY)
    const onWiden = () => {
      if (!narrow.matches) {
        exit()
      }
    }
    window.addEventListener('keydown', onKey)
    narrow.addEventListener('change', onWiden)
    return () => {
      window.removeEventListener('keydown', onKey)
      narrow.removeEventListener('change', onWiden)
      document.body.style.overflow = overflow
      if (cooperative) {
        gestures?.enable()
      }
    }
  }, [full, exit, mapRef])

  return [full, toggle]
}
