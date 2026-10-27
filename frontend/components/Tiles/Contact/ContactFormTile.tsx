'use client'

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BaseTile } from '../Base/BaseTile'

type Reason =
  | 'campaign'
  | 'sensebox-bike'
  | 'temperature-logger'
  | 'sensebox-edu'

interface FormState {
  name: string
  email: string
  institution: string
  reason: Reason | ''
  period: string
  message: string
}

const initialState: FormState = {
  name: '',
  email: '',
  institution: '',
  reason: '',
  period: '',
  message: '',
}

const inputClass =
  'w-full rounded-md border border-white/60 bg-white/50 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary'

const labelClass = 'block text-xs font-semibold text-gray-600 mb-1'

export default function ContactFormTile() {
  const { t } = useTranslation()
  const [form, setForm] = useState<FormState>(initialState)
  const [status, setStatus] = useState<
    'idle' | 'submitting' | 'success' | 'error'
  >('idle')

  const reasons: { value: Reason; label: string }[] = [
    { value: 'campaign', label: t('contactForm.reasonCampaign') },
    { value: 'sensebox-bike', label: t('contactForm.reasonSenseboxBike') },
    {
      value: 'temperature-logger',
      label: t('contactForm.reasonTemperatureLogger'),
    },
    { value: 'sensebox-edu', label: t('contactForm.reasonSenseboxEdu') },
  ]

  const set =
    (field: keyof FormState) =>
    (
      e: React.ChangeEvent<
        HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
      >,
    ) =>
      setForm(prev => ({ ...prev, [field]: e.target.value }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.reason) {
      return
    }

    setStatus('submitting')
    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        throw new Error('non-2xx')
      }
      setStatus('success')
      setForm(initialState)
    } catch {
      setStatus('error')
    }
  }

  return (
    <BaseTile hideFooter variant="primary">
      <div className="w-full">
        <div className="mx-auto w-full max-w-4xl rounded-xl border border-primary/20 bg-white/60 p-6 shadow-sm lg:p-8">
          <h2 className="mb-3 font-lexend text-2xl font-medium text-primary lg:text-3xl">
            {t('contactForm.title')}
          </h2>
          <p
            className="mb-6 text-sm text-gray-600"
            dangerouslySetInnerHTML={{ __html: t('contactForm.description') }}
          />

          {status === 'success' ? (
            <div className="rounded-lg bg-green-50 px-5 py-6 text-center">
              <p className="text-lg font-semibold text-green-700">
                {t('contactForm.successTitle')}
              </p>
              <p className="mt-1 text-sm text-green-600">
                {t('contactForm.successMessage')}
              </p>
            </div>
          ) : (
            <form className="space-y-4" noValidate onSubmit={handleSubmit}>
              {/* Name + Email row */}
              <div className="sm:grid-cols-2 grid grid-cols-1 gap-4">
                <div>
                  <label className={labelClass}>
                    {t('contactForm.name')}
                    <span className="ml-1 text-red-400">*</span>
                  </label>
                  <input
                    className={inputClass}
                    onChange={set('name')}
                    placeholder={t('contactForm.namePlaceholder')}
                    required
                    type="text"
                    value={form.name}
                  />
                </div>
                <div>
                  <label className={labelClass}>
                    {t('contactForm.email')}
                    <span className="ml-1 text-red-400">*</span>
                  </label>
                  <input
                    className={inputClass}
                    onChange={set('email')}
                    placeholder={t('contactForm.emailPlaceholder')}
                    required
                    type="email"
                    value={form.email}
                  />
                </div>
              </div>

              {/* Institution */}
              <div>
                <label className={labelClass}>
                  {t('contactForm.institution')}
                </label>
                <input
                  className={inputClass}
                  onChange={set('institution')}
                  placeholder={t('contactForm.institutionPlaceholder')}
                  type="text"
                  value={form.institution}
                />
              </div>

              {/* Reason dropdown */}
              <div>
                <label className={labelClass}>
                  {t('contactForm.reason')}
                  <span className="ml-1 text-red-400">*</span>
                </label>
                <select
                  className={inputClass}
                  onChange={set('reason')}
                  required
                  value={form.reason}
                >
                  <option disabled value="">
                    {t('contactForm.reasonPlaceholder')}
                  </option>
                  {reasons.map(r => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Period */}
              <div>
                <label className={labelClass}>{t('contactForm.period')}</label>
                <input
                  className={inputClass}
                  onChange={set('period')}
                  placeholder={t('contactForm.periodPlaceholder')}
                  type="text"
                  value={form.period}
                />
              </div>

              {/* Free text */}
              <div>
                <label className={labelClass}>{t('contactForm.message')}</label>
                <textarea
                  className={`${inputClass} min-h-[120px] resize-y`}
                  onChange={set('message')}
                  placeholder={t('contactForm.messagePlaceholder')}
                  rows={4}
                  value={form.message}
                />
              </div>

              {status === 'error' && (
                <p className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-600">
                  <strong>{t('contactForm.errorTitle')}: </strong>
                  {t('contactForm.errorMessage')}
                </p>
              )}

              <button
                className="rounded-md bg-primary px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary/90 disabled:opacity-60"
                disabled={
                  status === 'submitting' ||
                  !form.name ||
                  !form.email ||
                  !form.reason
                }
                type="submit"
              >
                {status === 'submitting'
                  ? t('contactForm.submitting')
                  : t('contactForm.submit')}
              </button>
            </form>
          )}
        </div>
      </div>
    </BaseTile>
  )
}
