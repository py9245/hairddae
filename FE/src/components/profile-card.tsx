import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import type { MeResponse } from '@/lib/auth'

type ProfileCardProps = {
  profile: MeResponse
  onLogout: () => void
  onDesignerApply: () => void
}

function getAvatarVariant(userId: string): 1 | 2 | 3 | 4 | 5 {
  let sum = 0
  for (let i = 0; i < userId.length; i++) {
    sum += userId.charCodeAt(i)
  }

  return ((sum % 5) + 1) as 1 | 2 | 3 | 4 | 5
}

export function ProfileCard({
  profile,
  onLogout,
  onDesignerApply,
}: ProfileCardProps) {
  const birthDateDisplay = profile.birthDate || '생년월일 비공개'
  const genderMap: Record<string, string> = { F: '여자', M: '남자' }
  const mappedGender = profile.gender
    ? (genderMap[profile.gender] ?? profile.gender)
    : null
  const genderDisplay = mappedGender || '성별 비공개'
  const grade = profile.grade ?? 0
  const isDesignerPending = grade === 1
  const isDesigner = grade === 2

  return (
    <section className="rounded-3xl bg-card p-6">
      <div className="flex items-center gap-3">
        <Avatar variant={getAvatarVariant(profile.userID)} />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate text-lg font-bold text-labels-primary">
              {profile.userID}
            </p>
            {isDesigner ? (
              <span className="shrink-0 rounded-full bg-primary-100 px-2.5 py-1 text-xs font-semibold text-primary-300">
                디자이너
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-sm text-labels-secondary">
            {birthDateDisplay} · {genderDisplay}
          </p>
        </div>
      </div>

      <Button variant="logout" size="full" className="mt-5" onClick={onLogout}>
        로그아웃
      </Button>

      {isDesigner ? null : (
        <Button
          variant="login"
          size="full"
          className="mt-3"
          onClick={onDesignerApply}
          disabled={isDesignerPending}
        >
          {isDesignerPending ? '디자이너 승인 대기중' : '디자이너 신청'}
        </Button>
      )}
    </section>
  )
}

export function ProfileCardSkeleton() {
  return (
    <section className="rounded-3xl bg-card p-6">
      <div className="flex items-center gap-3">
        <Avatar loading />
        <div className="space-y-2">
          <div className="h-5 w-28 animate-pulse rounded bg-muted" />
          <div className="h-4 w-20 animate-pulse rounded bg-muted" />
        </div>
      </div>
      <div className="mt-5 h-[52px] w-full animate-pulse rounded-xl bg-muted" />
      <div className="mt-3 h-[52px] w-full animate-pulse rounded-xl bg-muted" />
    </section>
  )
}
