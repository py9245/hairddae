import { DesignerListCard } from '@/components/designer-list-card'
import { Header } from '@/components/header'
import { readDesignerListCache } from '@/lib/Camera/designer'

export default function DesignerList() {
  const designers = readDesignerListCache()
  const designerCount = designers.length

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header label="디자이너" className="px-0 pb-3 pt-2" />

        <section className="rounded-[28px] bg-[linear-gradient(135deg,#FBE3E8_0%,#FFFFFF_100%)] px-5 py-6 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
          <p className="text-sm font-semibold text-primary-300">
            위치 기반 추천
          </p>
          <h1 className="mt-2 text-[24px] font-bold leading-8 text-text-dark">
            {designerCount > 0
              ? `주변 디자이너 ${designerCount}명을 불러왔어요`
              : '추천 디자이너를 준비하고 있어요'}
          </h1>
        </section>

        <section className="mt-5 flex flex-col gap-4 pb-6">
          {designerCount > 0 ? (
            designers.map((designer, index) => (
              <DesignerListCard
                key={`${designer.id}-${designer.name}`}
                designer={designer}
                rank={index + 1}
              />
            ))
          ) : (
            <div className="rounded-[28px] bg-card px-5 py-10 text-center shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
              <p className="text-base font-semibold text-text-dark">
                불러온 디자이너 정보가 없습니다.
              </p>
              <p className="mt-2 text-sm leading-6 text-text-sub">
                카메라 화면에서 다시 디자이너 찾기를 시도해주세요.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
