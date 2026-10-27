'use client'

import Title from '@/components/Elements/Title'

export default function Impressum() {
  return (
    <main className="mx-auto max-w-[1136px]">
      <div className="h-12 md:h-24 lg:h-64" />
      <Title as="h3" id="feedback" variant={'primary'}>
        Sie haben Feedback?
      </Title>
      <div className="h-6" />
      <Title className="text-2xl">
        Wir arbeiten stetig daran, unser Dashboard zu optimieren und freuen uns
        über Feedback. Ihnen fehlen entscheidende Informationen? Sie stoßen auf
        technische Probleme? Sie haben Ideen für Verbesserungen, von denen das
        Klimadashboard profitieren könnte? Wir freuen uns auf Ihre Nachricht.
      </Title>
      <div className="h-12 md:h-24 lg:h-64" />
    </main>
  )
}
