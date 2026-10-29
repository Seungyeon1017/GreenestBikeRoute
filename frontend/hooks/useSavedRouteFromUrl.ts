import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import { fetchSavedRoutes } from '@/services/usersApi'
import type { SavedRoute } from '@/types/users'

/**
 * Opens a saved route when Plan a Trip is reached from the Profile tab
 * (/plan-trip?saved=<id>): once the map is ready and the login is known, it
 * looks the route up and hands it to `open`. Runs once per page visit.
 * Returns an error message if the route couldn't be opened.
 */
export default function useSavedRouteFromUrl(
  mapReady: boolean,
  open: (_route: SavedRoute) => void,
): string | null {
  const { t } = useTranslation()
  const { status, token } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const done = useRef(false)
  // The latest `open`, without re-running the effect when the page re-renders.
  const openRef = useRef(open)
  openRef.current = open

  useEffect(() => {
    if (done.current || !mapReady || status === 'loading') {
      return
    }
    done.current = true
    const id = Number(new URLSearchParams(window.location.search).get('saved'))
    if (!id) {
      return
    }
    // Drop ?saved= from the address, so reloading the page doesn't reopen it over new changes.
    window.history.replaceState(null, '', window.location.pathname)
    if (!token) {
      setError(t('greenest.planTrip.save.loginToOpen'))
      return
    }
    fetchSavedRoutes(token)
      .then(routes => {
        const route = routes.find(r => r.id === id)
        if (route) {
          openRef.current(route)
        } else {
          setError(t('greenest.planTrip.save.notFound'))
        }
      })
      .catch((err: Error) => setError(err.message))
  }, [mapReady, status, token, t])

  return error
}
