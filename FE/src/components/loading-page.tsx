export function LoadingPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-bg-primary">
      <div className="animate-pulse flex flex-col items-center gap-6">
        <img src="/icon/logo.svg" alt="로고" className="h-12 w-auto" />
        <p className="text-base font-normal leading-[140%] text-labels-primary">
          잠시만 기다려주세요...
        </p>
      </div>
    </div>
  )
}
