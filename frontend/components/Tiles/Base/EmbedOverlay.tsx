'use client'

import AnimatedCopyIcon from '@/components/Elements/Animated/AnimatedCopyIcon'
import { Button } from '@/components/Elements/Button'
import Title from '@/components/Elements/Title'
import { TileType } from '@/utils/TileFactory'
import { ClipboardDocumentIcon } from '@heroicons/react/24/outline'
import { AnimatedProps } from '@react-spring/web'
import { ComponentPropsWithRef } from 'react'
import BaseOverlay from './BaseOverlay'
import { useTranslation } from 'react-i18next'

type EmbedOverlayProps = AnimatedProps<ComponentPropsWithRef<'div'>> & {
  onClose?: () => void
  embedId: TileType
}

export default function EmbedOverlay({
  onClose,
  embedId,
  ...props
}: EmbedOverlayProps) {
  const { t } = useTranslation()
  const link = `${window.location.origin}/embed/${embedId}`

  const iframeSrc = `<iframe src="${link}" style="border:none; width:100%; height:100%" title="Dashboard"></iframe>`

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(iframeSrc)
  }

  return (
    <BaseOverlay onClose={onClose} {...props}>
      <div className="flex h-full w-full flex-1 flex-col">
        <div className="grid grid-flow-col grid-cols-3 grid-rows-2 gap-8">
          <div className="col-span-2 row-span-1">
            <Title as="h3" variant={'inverse'}>
              {t('embedOverlay.title')}
            </Title>
          </div>
          <div className="col-span-2 row-span-1">
            <div className="flex rounded bg-white p-4">
              <pre className="m-4 flex-1 whitespace-pre-wrap break-all text-sm">
                {iframeSrc}
              </pre>
              <div className="relative w-7">
                <AnimatedCopyIcon onClick={copyToClipboard} />
              </div>
            </div>
          </div>
          <div className="col-span-1 row-span-2">
            <p className="text-white">
              {t('embedOverlay.description')}
            </p>
          </div>
        </div>
        <div className="pt-10">
          <Button
            onClick={copyToClipboard}
            startIcon={
              <ClipboardDocumentIcon className="w-5 stroke-2 text-secondary" />
            }
            variant={'overlay'}
          >
            {t('embedOverlay.copyCode')}
          </Button>
        </div>
      </div>
    </BaseOverlay>
  )
}
