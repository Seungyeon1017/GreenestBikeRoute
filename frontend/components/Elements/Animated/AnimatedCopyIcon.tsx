import { CheckIcon, ClipboardDocumentIcon } from '@heroicons/react/24/outline'
import { animated, useTransition } from '@react-spring/web'
import { useEffect, useState } from 'react'

type AnimatedCopyIconProps = {
  onClick: () => void
}

export default function AnimatedCopyIcon({ onClick }: AnimatedCopyIconProps) {
  const [success, setSuccess] = useState(false)

  useEffect(() => {
    if (!success) {
      return
    }

    setTimeout(() => setSuccess(false), 2000)
  }, [success])

  const transitions = useTransition(success, {
    from: { opacity: 0 },
    enter: { opacity: 1 },
    leave: { opacity: 0 },
  })

  const handleOnClick = () => {
    onClick()
    setSuccess(true)
  }

  return transitions((styles, isSuccess) => (
    // @ts-ignore
    <animated.div
      className="absolute top-0 cursor-pointer rounded-lg bg-transparent p-2 hover:bg-zinc-100"
      onClick={handleOnClick}
      style={styles}
    >
      {isSuccess ? (
        <CheckIcon className="w-5 stroke-2 text-secondary" />
      ) : (
        <ClipboardDocumentIcon className="w-5 stroke-2 text-primary" />
      )}
    </animated.div>
  ))
}
