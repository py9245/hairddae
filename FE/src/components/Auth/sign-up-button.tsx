import type * as React from 'react'

import { Button } from '@/components/ui/button'

type SignUpButtonProps = Omit<
  React.ComponentProps<typeof Button>,
  'children' | 'variant' | 'size'
> & {
  isPending?: boolean
  children?: React.ReactNode
}

function SignUpButton({
  isPending = false,
  disabled,
  children,
  ...props
}: SignUpButtonProps) {
  return (
    <Button
      variant="login"
      size="splash"
      type="submit"
      aria-busy={isPending || undefined}
      disabled={disabled || isPending}
      {...props}
    >
      {children ?? (isPending ? '가입 중...' : '가입하기')}
    </Button>
  )
}

export { SignUpButton }
