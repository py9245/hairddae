import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import type { MeResponse } from '@/lib/auth'

interface ProfileCardProps {
  profile: MeResponse
  onLogout: () => void
}

function getAvatarVariant(userId: string): 1 | 2 | 3 | 4 | 5 {
  let sum = 0
  for (let i = 0; i < userId.length; i++) {
    sum += userId.charCodeAt(i)
  }
  return ((sum % 5) + 1) as 1 | 2 | 3 | 4 | 5
}

export function ProfileCard({ profile, onLogout }: ProfileCardProps) {
  const birthDateDisplay = profile.birthDate
    ? profile.birthDate
    : '생년월일 비공개'

  const genderMap: Record<string, string> = { F: '여자', M: '남자' }
  const mappedGender = profile.gender
    ? (genderMap[profile.gender] ?? profile.gender)
    : null

  const genderDisplay =
    mappedGender == null || mappedGender === '' ? '성별 비공개' : mappedGender

  return (
    <section className="rounded-3xl bg-card p-6">
      <div className="flex items-center gap-3">
        <Avatar variant={getAvatarVariant(profile.userID)} />
        <div>
          <p className="text-lg font-bold text-labels-primary">
            {profile.userID}
          </p>
          <p className="mt-1 text-sm text-labels-secondary">
            {birthDateDisplay} · {genderDisplay}
          </p>
        </div>
      </div>
      <Button variant="logout" size="full" className="mt-5" onClick={onLogout}>
        로그아웃
      </Button>
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
    </section>
  )
}
