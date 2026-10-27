'use client'

import CookieConsent from 'react-cookie-consent'
import { useTranslation } from 'react-i18next'

export default function Cookies() {
  const { t } = useTranslation()
  return (
    <CookieConsent
      buttonStyle={{
        background: '#aab315',
        color: '#fff',
        borderRadius: '4px',
      }}
      buttonText={t('cookies.accept')}
      declineButtonStyle={{
        borderRadius: '4px',
      }}
      declineButtonText={t('cookies.decline')}
      enableDeclineButton
      style={{
        background: '#005b79',
      }}
    >
      {t('cookies.message')}
    </CookieConsent>
  )
}
