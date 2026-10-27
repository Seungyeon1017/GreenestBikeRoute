'use client'

import dynamic from 'next/dynamic'
import MapSkeleton from './MapSkeleton'

/** BaseMap loaded only in the browser, since MapLibre needs `window`. */
const BaseMap = dynamic(() => import('./BaseMap'), {
  ssr: false,
  loading: () => <MapSkeleton />,
})

export default BaseMap
export { HEILBRONN_CENTER } from './BaseMap'
