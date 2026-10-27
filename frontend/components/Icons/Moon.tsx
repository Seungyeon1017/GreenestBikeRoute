import * as React from 'react'
import type { SVGProps } from 'react'
function SvgMoon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 1200 1200" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M600 300c71.039 0 128.52 134.28 128.52 300S671.04 900 600 900a300 300 0 0 0 212.13-512.127A300 300 0 0 0 600 300.006z" />
    </svg>
  )
}
export default SvgMoon
