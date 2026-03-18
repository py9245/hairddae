import { useEffect } from 'react'

declare global {
  interface Window {
    adsbygoogle: unknown[]
  }
}

export default function Adsense() {
  useEffect(() => {
    try {
      ;(window.adsbygoogle = window.adsbygoogle || []).push({})
    } catch (e) {
      console.error('AdSense error:', e)
    }
  }, [])

  return (
    <aside className="hidden w-[450px] shrink-0 xl:block">
      <div className="sticky top-6 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <p className="mb-3 text-sm font-semibold text-slate-700">광고</p>

        <ins
          className="adsbygoogle block overflow-hidden rounded-xl"
          style={{ display: 'block', width: '100%', height: '600px' }}
          data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
          data-ad-slot="1234567890"
          data-ad-format="auto"
          data-full-width-responsive="true"
        />
      </div>
    </aside>
  )
}