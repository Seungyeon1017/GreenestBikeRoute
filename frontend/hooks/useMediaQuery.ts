import { useEffect, useState } from 'react'

/** Whether the window matches a CSS media query, e.g. '(min-width: 1024px)'. False on the server. */
export default function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    const list = window.matchMedia(query)
    setMatches(list.matches)
    const onChange = () => setMatches(list.matches)
    list.addEventListener('change', onChange)
    return () => list.removeEventListener('change', onChange)
  }, [query])

  return matches
}
