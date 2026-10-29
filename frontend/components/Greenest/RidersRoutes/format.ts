/** "12.4 km" */
export function km(metres: number): string {
  return `${(metres / 1000).toFixed(1)} km`
}

/** "45 min", "1 h 20 min" */
export function rideTime(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  return minutes < 60
    ? `${minutes} min`
    : `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')} min`
}

/** "6. Sept. 2026" for "2026-09-06", in the page language. */
export function day(isoDate: string, language: string): string {
  return new Date(`${isoDate.slice(0, 10)}T12:00:00`).toLocaleDateString(
    language,
    { dateStyle: 'medium' },
  )
}
