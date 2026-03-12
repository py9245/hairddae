import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import type { UserProfile } from '@/lib/mock/mock-profile'

interface ProfileCardProps {
  profile: UserProfile
  onLogout: () => void
}

export function ProfileCard({ profile, onLogout }: ProfileCardProps) {
  const ageDisplay = profile.age == null ? '비공개' : `${profile.age}세`

  const genderMap: Record<string, string> = { F: '여자', M: '남자' }
  const mappedGender = profile.gender ? (genderMap[profile.gender] ?? profile.gender) : null

  const genderDisplay =
    mappedGender == null || mappedGender === '' ? '비공개' : mappedGender

  return (
    <section className="rounded-3xl bg-card p-6">
      <div className="flex items-center gap-3">
        <Avatar variant={profile.avatarVariant} />
        <div>
          <p className="text-lg font-bold text-labels-primary">
            {profile.nickname}
          </p>
          <p className="mt-1 text-sm text-labels-secondary">
            {ageDisplay} · {genderDisplay}
          </p>
        </div>
      </div>
      <Button
        variant="logout"
        size="full"
        className="mt-5"
        onClick={onLogout}
      >
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
