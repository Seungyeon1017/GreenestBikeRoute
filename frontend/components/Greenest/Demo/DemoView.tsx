'use client'

import { ArrowRight, ExternalLink, Play } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import PageIntro from '@/components/Greenest/ui/PageIntro'

const VIDEO_ID = 'tV64fzAv0Lk'
const VIDEO_URL = `https://youtu.be/${VIDEO_ID}`
const EMBED_URL = `https://www.youtube-nocookie.com/embed/${VIDEO_ID}?autoplay=1&mute=1&playsinline=1&rel=0`

/** Loads the YouTube player only after a click, so nothing reaches Google before it. */
export default function DemoView() {
  const { t } = useTranslation()
  const [playing, setPlaying] = useState(false)

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 px-4 py-6 md:px-8">
      <PageIntro title={t('greenest.demo.title')} />
      <div className="relative aspect-video overflow-hidden rounded-2xl border border-leaf-forest/15 bg-leaf-forest shadow-sm">
        {playing ? (
          <iframe
            allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
            allowFullScreen
            className="absolute inset-0 h-full w-full"
            // YouTube's player refuses to start without the site's origin.
            referrerPolicy="strict-origin-when-cross-origin"
            src={EMBED_URL}
            title={t('greenest.demo.title')}
          />
        ) : (
          <button
            aria-label={t('greenest.demo.play')}
            className="group/video absolute inset-0 block h-full w-full focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-4 focus-visible:outline-leaf-cream"
            onClick={() => setPlaying(true)}
            type="button"
          >
            <Image
              alt=""
              className="object-cover transition duration-200 group-hover/video:scale-[1.01]"
              fill
              priority
              sizes="(min-width: 896px) 832px, 100vw"
              src="/demo/poster.webp"
              unoptimized
            />
            {/* In the corner: the poster's title sits in the middle. */}
            <span className="absolute inset-0 flex items-end justify-end bg-leaf-ink/5 p-3 transition group-hover/video:bg-leaf-ink/15 md:p-5">
              <span className="grid h-12 w-12 place-items-center rounded-full bg-leaf-forest text-leaf-cream shadow-lg transition group-hover/video:scale-105 md:h-16 md:w-16">
                <Play
                  aria-hidden
                  className="ml-0.5 h-5 w-5 fill-current md:h-7 md:w-7"
                />
              </span>
            </span>
          </button>
        )}
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link
          className="inline-flex items-center justify-center gap-2 rounded-full bg-leaf-forest px-5 py-2.5 text-sm font-medium text-leaf-cream hover:opacity-90"
          href="/overview"
        >
          {t('greenest.demo.tryApp')}
          <ArrowRight aria-hidden className="h-4 w-4" />
        </Link>
        <a
          className="inline-flex items-center justify-center gap-2 rounded-full border border-leaf-forest/30 px-5 py-2.5 text-sm font-medium text-leaf-forest hover:bg-leaf-forest/5"
          href={VIDEO_URL}
          rel="noreferrer"
          target="_blank"
        >
          {t('greenest.demo.watch')}
          <ExternalLink aria-hidden className="h-4 w-4" />
        </a>
      </div>
      <p className="text-xs leading-relaxed text-leaf-muted">
        {t('greenest.demo.privacy')}{' '}
        <Link className="underline underline-offset-2" href="/datenschutz">
          {t('footer.datenschutz')}
        </Link>
      </p>
    </div>
  )
}
