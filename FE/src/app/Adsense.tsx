import { useEffect } from 'react'

declare global {
  interface Window {
    adsbygoogle: unknown[]
  }
}

type AdsenseProps = {
  loading?: boolean
}

export default function Adsense({ loading = false }: AdsenseProps) {
  useEffect(() => {
    if (loading) return

    try {
      ;(window.adsbygoogle = window.adsbygoogle || []).push({})
    } catch (e) {
      console.error('AdSense error:', e)
    }
  }, [loading])

  return (
    <aside className="hidden w-[450px] shrink-0 xl:block">
      <div className="sticky top-6 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <p className="mb-3 text-sm font-semibold text-slate-700">광고</p>

        <div className="flex min-h-[350px] items-center justify-center rounded-xl bg-white">
          {loading ? (
            <div className="w-full max-w-[336px]">
              <div className="h-[280px] animate-pulse rounded-xl border border-gray-200 bg-gray-100" />
            </div>
          ) : (
            <div className="w-full max-w-[336px]">
              <ins  
                className="adsbygoogle block w-full"
                style={{ display: 'block' }}
                data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
                data-ad-slot="1234567890"
                data-ad-format="auto"
                data-full-width-responsive="true"
              />
            </div>
          )}
        </div>
      </div>
    </aside>
  )
}