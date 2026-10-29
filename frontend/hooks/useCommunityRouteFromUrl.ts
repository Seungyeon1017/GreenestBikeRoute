import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import { fetchCommunityRoute } from '@/services/communityRoutesApi'
import type { CommunityRoute } from '@/types/users'

/**
 * Plan trip opened with ?route=<id> (a riders' leisure route from Highlights,
 * the Profile tab or a shared link) or ?contribute=1 (upload your own). Once
 * the map is ready and the login is known, loads the route (with whether you
 * hearted or saved it) and hands it to `open`. Runs once per page visit.
 */
export default function useCommunityRouteFromUrl(
  mapReady: boolean,
  open: (_route: CommunityRoute) => void,
): { error: string | null; contribute: boolean } {
  const { t } = useTranslation()
  const { status, token } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [contribute, setContribute] = useState(false)
  const done = useRef(false)
  const openRef = useRef(open)
  openRef.current = open

  useEffect(() => {
    if (done.current || !mapReady || status === 'loading') {
      return
    }
    done.current = true
    const params = new URLSearchParams(window.location.search)
    const id = Number(params.get('route'))
    if (params.get('contribute')) {
      setContribute(true)
    }
    if (!id && !params.get('contribute')) {
      return
    }
    window.history.replaceState(null, '', window.location.pathname)
    if (!id) {
      return
    }
    fetchCommunityRoute(token, id)
      .then(route => openRef.current(route))
      .catch((err: Error & { status?: number }) =>
        setError(
          err.status === 404
            ? t('greenest.ridersRoutes.notFound')
            : err.message,
        ),
      )
  }, [mapReady, status, token, t])

  return { error, contribute }
}
