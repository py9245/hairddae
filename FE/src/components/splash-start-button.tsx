import type * as React from 'react'

import { Button } from '@/components/ui/button'

type SplashStartButtonProps = Omit<
  React.ComponentProps<typeof Button>,
  'variant' | 'size'
>

function SplashStartButton({
  children = '헤어 어때 시작하기',
  ...props
}: SplashStartButtonProps) {
  return (
    <Button variant="splash" size="splash" {...props}>
      {children}
    </Button>
  )
}

export { SplashStartButton }
