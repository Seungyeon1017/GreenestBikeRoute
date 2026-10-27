'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BIRD_SPECIES, type BirdSpecies } from './birdSpecies'

interface Detection {
  latinName: string
  germanName: string
  score: number
}

interface Movement {
  station_id: string
  mov_id: string
  start_date: string
  weight?: number
  detections: Detection[]
  video: string
  audio?: string
}

interface BirdiaryValidationTileProps {
  stationIds: string[]
}

type UIState = 'loading' | 'ready' | 'submitting' | 'error'

export default function BirdiaryValidationTile({
  stationIds,
}: BirdiaryValidationTileProps) {
  const { t } = useTranslation()
  const [movement, setMovement] = useState<Movement | null>(null)
  const [uiState, setUiState] = useState<UIState>('loading')
  // selected AI chip
  const [selectedDetection, setSelectedDetection] = useState<Detection | null>(null)
  // manual species override from combobox
  const [manualSpecies, setManualSpecies] = useState<BirdSpecies | null>(null)
  const [speciesQuery, setSpeciesQuery] = useState('')
  const [showDropdown, setShowDropdown] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const effectiveSpecies = manualSpecies ?? selectedDetection

  const filteredSpecies = speciesQuery.length >= 1
    ? BIRD_SPECIES.filter(s =>
        s.germanName.toLowerCase().includes(speciesQuery.toLowerCase()) ||
        s.latinName.toLowerCase().includes(speciesQuery.toLowerCase()),
      ).slice(0, 8)
    : []

  const fetchNext = useCallback(async () => {
    setUiState('loading')
    setMovement(null)
    setSelectedDetection(null)
    setManualSpecies(null)
    setSpeciesQuery('')
    setShowDropdown(false)
    try {
      const params = new URLSearchParams({ stationIds: stationIds.join(',') })
      const res = await fetch(`/api/birdiary-validate?${params}`)
      if (!res.ok) { throw new Error('fetch failed') }
      const data: Movement = await res.json()
      setMovement(data)
      setSelectedDetection(data.detections?.[0] ?? null)
      setUiState('ready')
    } catch {
      setUiState('error')
    }
  }, [stationIds])

  useEffect(() => { fetchNext() }, [fetchNext])

  const pickDetection = (d: Detection) => {
    setSelectedDetection(d)
    setManualSpecies(null)
    setSpeciesQuery('')
    setShowDropdown(false)
  }

  const pickSpecies = (s: BirdSpecies) => {
    setManualSpecies(s)
    setSelectedDetection(null)
    setSpeciesQuery(s.germanName)
    setShowDropdown(false)
  }

  const submitValidation = async (isBird: boolean) => {
    if (!movement) { return }
    setUiState('submitting')
    try {
      await fetch('/api/birdiary-validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stationId: movement.station_id,
          movId: movement.mov_id,
          isBird,
          latinName: effectiveSpecies?.latinName ?? '',
          germanName: effectiveSpecies?.germanName ?? '',
        }),
      })
    } catch {
      // best-effort; move to next anyway
    }
    fetchNext()
  }

  const formatDate = (dateStr: string) => {
    try {
      return new Intl.DateTimeFormat('de-DE', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      }).format(new Date(dateStr.replace(' ', 'T')))
    } catch {
      return dateStr
    }
  }

  return (
    <div className="w-full">
      {/* Loading */}
      {uiState === 'loading' && (
        <div className="flex h-64 items-center justify-center">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-climate border-t-transparent" />
        </div>
      )}

      {/* Error */}
      {uiState === 'error' && (
        <div className="rounded-lg bg-red-50 px-5 py-6 text-center">
          <p className="text-base text-red-600">
            {t('birdiaryValidation.loadError')}
          </p>
          <button
            className="mt-4 rounded-lg border-2 border-climate px-5 py-2.5 text-base font-medium text-climate hover:bg-climate/10"
            onClick={fetchNext}
          >
            {t('birdiaryValidation.retry')}
          </button>
        </div>
      )}

      {/* Ready / Submitting */}
      {(uiState === 'ready' || uiState === 'submitting') && movement && (
        <div className="flex flex-col gap-6 lg:flex-row">
          {/* Video */}
          <div className="overflow-hidden rounded-lg bg-black lg:w-1/2">
            <video
              autoPlay
              className="w-full rounded-lg"
              controls
              key={movement.mov_id}
              loop
              muted
              playsInline
              ref={videoRef}
              src={movement.video}
            >
              <track kind="captions" />
            </video>
          </div>

          {/* Controls */}
          <div className="flex flex-col gap-5 lg:w-1/2">
            {/* Description */}
            <p className="text-base text-gray-600">
              {t('birdiaryValidation.description')}
            </p>

            {/* Metadata */}
            <div className="flex flex-wrap gap-4 text-sm text-gray-500">
              <span>
                <span className="font-semibold text-gray-700">
                  {t('birdiaryValidation.date')}:
                </span>{' '}
                {formatDate(movement.start_date)}
              </span>
              {movement.weight != null && (
                <span>
                  <span className="font-semibold text-gray-700">
                    {t('birdiaryValidation.weight')}:
                  </span>{' '}
                  {Math.round(movement.weight * 10) / 10} g
                </span>
              )}
            </div>

            {/* AI Detections */}
            {movement.detections.length > 0 && (
              <div>
                <p className="mb-2 text-sm font-semibold text-gray-600">
                  {t('birdiaryValidation.aiDetection')}:
                </p>
                <div className="flex flex-wrap gap-2">
                  {movement.detections.map(d => (
                    <button
                      className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors ${
                        selectedDetection?.latinName === d.latinName
                          ? 'border-climate bg-climate text-white'
                          : 'border-gray-300 bg-white/70 text-gray-700 hover:border-climate hover:text-climate'
                      }`}
                      key={d.latinName}
                      onClick={() => pickDetection(d)}
                    >
                      {d.germanName || d.latinName}{' '}
                      <span className="opacity-60">
                        ({Math.round(d.score * 100)}%)
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Species combobox */}
            <div className="relative" ref={dropdownRef}>
              <p className="mb-2 text-sm font-semibold text-gray-600">
                {t('birdiaryValidation.speciesSearch')}
              </p>
              <input
                className={`w-full rounded-lg border px-4 py-2.5 text-base outline-none transition-colors placeholder:text-gray-400 ${
                  manualSpecies
                    ? 'border-climate bg-climate/5 text-climate'
                    : 'border-gray-300 bg-white/80 text-gray-800 focus:border-climate'
                }`}
                onChange={e => {
                  setSpeciesQuery(e.target.value)
                  setManualSpecies(null)
                  setShowDropdown(true)
                }}
                onFocus={() => { if (speciesQuery.length >= 1) { setShowDropdown(true) } }}
                placeholder={t('birdiaryValidation.speciesSearchPlaceholder')}
                type="text"
                value={speciesQuery}
              />
              {showDropdown && speciesQuery.length >= 1 && (
                <div className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg">
                  {filteredSpecies.length === 0 ? (
                    <p className="px-4 py-3 text-sm text-gray-400">
                      {t('birdiaryValidation.speciesNoResults')}
                    </p>
                  ) : (
                    filteredSpecies.map(s => (
                      <button
                        className="flex w-full items-baseline gap-2 px-4 py-2.5 text-left text-sm hover:bg-climate/10"
                        key={s.latinName}
                        onMouseDown={() => pickSpecies(s)}
                        type="button"
                      >
                        <span className="font-medium text-gray-800">{s.germanName}</span>
                        <span className="text-xs italic text-gray-400">{s.latinName}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Action buttons */}
            <div className="flex flex-wrap gap-3">
              <button
                className="rounded-lg bg-climate px-6 py-3 text-base font-semibold text-white transition-colors hover:bg-climate/80 disabled:opacity-50"
                disabled={uiState === 'submitting'}
                onClick={() => submitValidation(true)}
              >
                {t('birdiaryValidation.birdInVideo')}
              </button>
              <button
                className="rounded-lg border-2 border-climate px-6 py-3 text-base font-semibold text-climate transition-colors hover:bg-climate/10 disabled:opacity-50"
                disabled={uiState === 'submitting'}
                onClick={() => submitValidation(false)}
              >
                {t('birdiaryValidation.noBird')}
              </button>
              <button
                className="rounded-lg border-2 border-gray-300 px-6 py-3 text-base font-semibold text-gray-600 transition-colors hover:border-gray-400 hover:text-gray-800 disabled:opacity-50"
                disabled={uiState === 'submitting'}
                onClick={fetchNext}
              >
                {t('birdiaryValidation.dontKnow')}
              </button>
            </div>

            {uiState === 'submitting' && (
              <p className="text-sm text-gray-400">
                {t('birdiaryValidation.submitting')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

