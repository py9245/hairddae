export interface UserProfile {
  nickname: string
  age: number | null
  gender: string | null
  avatarVariant: 1 | 2 | 3 | 4 | 5
}

const MOCK_PROFILE: UserProfile = {
  nickname: 'mijin.develop',
  age: 18,
  gender: 'F',
  avatarVariant: 1,
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function fetchProfile(): Promise<UserProfile> {
  await delay(800)
  return MOCK_PROFILE
}
