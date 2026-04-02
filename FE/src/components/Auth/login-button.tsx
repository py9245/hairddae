import type * as React from 'react'

import { Button } from '@/components/ui/button'

type LoginButtonProps = Omit<
  React.ComponentProps<typeof Button>,
  'children' | 'variant' | 'size'
> & {
  isPending?: boolean
  children?: React.ReactNode
}

function LoginButton({
  isPending = false,
  disabled,
  children,
  ...props
}: LoginButtonProps) {
  return (
    <Button
      variant="login"
      size="splash"
      type="submit"
      aria-busy={isPending || undefined}
      disabled={disabled || isPending}
      {...props}
    >
      {children ?? (isPending ? '로그인 중...' : '로그인')}
    </Button>
  )
}

export { LoginButton }
