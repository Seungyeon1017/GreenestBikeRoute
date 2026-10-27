import { useEffect, useState } from 'react'
import { fetchOverviewData, type OverviewData } from '@/services/mapData'

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: OverviewData }

export default function useOverviewData(): State {
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    fetchOverviewData(controller.signal)
      .then(data => setState({ status: 'ready', data }))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') {
          setState({ status: 'error', message: error.message })
        }
      })
    return () => controller.abort()
  }, [])

  return state
}
