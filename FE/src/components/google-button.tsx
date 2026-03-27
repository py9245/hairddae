import type * as React from 'react'
import { cn } from '@/lib/utils'

type GoogleButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  label?: string
}

function GoogleIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18" className="h-5 w-5 shrink-0">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.56 2.68-3.86 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.33-1.58-5.04-3.7H.96v2.32A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.96 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.28-1.72V4.96H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.04l3-2.32Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.46 3.44 1.36l2.58-2.58C13.46.9 11.43 0 9 0A9 9 0 0 0 .96 4.96l3 2.32c.7-2.12 2.7-3.7 5.04-3.7Z"
      />
    </svg>
  )
}

function GoogleButton({
  className,
  disabled,
  label = 'Continue with Google',
  type = 'button',
  ...props
}: GoogleButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-14 w-full max-w-[400px] min-w-min select-none items-center overflow-hidden rounded-[4px] border border-[#747775] bg-white px-4 text-center align-middle font-["Roboto",arial,sans-serif] text-sm tracking-[0.25px] whitespace-nowrap text-[#1f1f1f] outline-none transition-[background-color,border-color,box-shadow] duration-[218ms] ease-linear',
        'hover:shadow-[0_1px_2px_0_rgba(60,64,67,0.30),0_1px_3px_1px_rgba(60,64,67,0.15)]',
        'focus-visible:shadow-[0_0_0_3px_rgba(48,48,48,0.12)]',
        'disabled:cursor-default disabled:border-[#1f1f1f1f] disabled:bg-[#ffffff61] disabled:shadow-none',
        className,
      )}
      {...props}
    >
      <span className="absolute inset-0 opacity-0 transition-opacity duration-[218ms] ease-linear hover:bg-[#303030]/[0.08] active:opacity-100 active:bg-[#303030]/[0.12] focus-visible:opacity-100 focus-visible:bg-[#303030]/[0.12]" />
      <span className="relative flex w-full items-center justify-between gap-2">
        <span className="flex h-5 w-5 items-center justify-center">
          <GoogleIcon />
        </span>
        <span className="grow overflow-hidden text-ellipsis font-medium">
          {label}
        </span>
        <span className="h-5 w-5 shrink-0" />
      </span>
    </button>
  )
}

export { GoogleButton }
