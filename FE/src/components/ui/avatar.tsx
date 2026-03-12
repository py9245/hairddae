type AvatarVariant = 1 | 2 | 3 | 4 | 5

const AVATAR_SOURCES: Record<AvatarVariant, string> = {
  1: '/icon/avatar-profile-01.svg',
  2: '/icon/avatar-profile-02.svg',
  3: '/icon/avatar-profile-03.svg',
  4: '/icon/avatar-profile-04.svg',
  5: '/icon/avatar-profile-05.svg',
}

interface AvatarProps {
  variant?: AvatarVariant
  loading?: boolean
}

export function Avatar({ variant = 1, loading = false }: AvatarProps) {
  if (loading) {
    return (
      <div className="size-10 shrink-0 rounded-full bg-muted animate-pulse" />
    )
  }

  return (
    <img
      src={AVATAR_SOURCES[variant]}
      alt="프로필 아바타"
      className="size-10 shrink-0 rounded-full"
    />
  )
}
