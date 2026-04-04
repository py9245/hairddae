import { apiFetch } from '@/lib/api'

const DESIGNER_LIST_STORAGE_KEY = 'camera-designer-list'

export type DesignerListItem = {
  id: number | string
  name: string
  salonName?: string | null
  profileImageUrl?: string | null
  address?: string | null
  distance?: string | null
  description?: string | null
}

export type GetDesignerRequest = {
  latitude: number
  longitude: number
  hairId: number
}

export type GetDesignerResponse = {
  code: number
  message: string
  designers: DesignerListItem[]
}

type RawDesigner = Partial<{
  id: number | string
  designer_id: number | string
  user_id: number | string
  userId: number | string
  name: string
  designer_name: string
  username: string
  salon_name: string
  shop_name: string
  address: string
  salon_address: string
  salonAddress: string
  distance: string | number
  distanceKm: string | number
  description: string
  intro: string
  profile_image_url: string
  image_url: string
}>

type RawDesignerResponse = Partial<{
  code: number
  message: string
  designers: RawDesigner[]
  designerList: RawDesigner[]
  results: RawDesigner[]
  items: RawDesigner[]
  data:
    | RawDesigner[]
    | Partial<{
        designers: RawDesigner[]
        designerList: RawDesigner[]
        results: RawDesigner[]
        items: RawDesigner[]
      }>
}>

function normalizeDistance(value: string | number | null | undefined) {
  if (value == null) {
    return null
  }

  if (typeof value === 'number') {
    return `${value}km`
  }

  return value.endsWith('km') ? value : `${value}km`
}

function normalizeDesigner(
  designer: RawDesigner,
  index: number,
): DesignerListItem {
  const id =
    designer.id ??
    designer.designer_id ??
    designer.user_id ??
    designer.userId ??
    `designer-${index + 1}`

  return {
    id,
    name:
      designer.name ??
      (typeof designer.userId === 'string' ? designer.userId : undefined) ??
      designer.designer_name ??
      designer.username ??
      `디자이너 ${index + 1}`,
    salonName: designer.salon_name ?? designer.shop_name ?? null,
    profileImageUrl: designer.profile_image_url ?? designer.image_url ?? null,
    address:
      designer.address ??
      designer.salonAddress ??
      designer.salon_address ??
      null,
    distance: normalizeDistance(designer.distanceKm ?? designer.distance),
    description: designer.description ?? designer.intro ?? null,
  }
}

function extractDesigners(
  data: RawDesignerResponse | null,
): DesignerListItem[] {
  const list =
    data?.designers ??
    data?.designerList ??
    data?.results ??
    data?.items ??
    (Array.isArray(data?.data)
      ? data.data
      : (data?.data?.designers ??
        data?.data?.designerList ??
        data?.data?.results ??
        data?.data?.items)) ??
    []

  if (!Array.isArray(list)) {
    return []
  }

  return list.slice(0, 5).map(normalizeDesigner)
}

export async function postGetDesigner({
  latitude,
  longitude,
  hairId,
}: GetDesignerRequest): Promise<GetDesignerResponse> {
  const response = await apiFetch('/camera/get-designer/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      latitude,
      longitude,
      hair_id: hairId,
    }),
  })

  const data = (await response
    .json()
    .catch(() => null)) as RawDesignerResponse | null

  if (!response.ok) {
    throw new Error(data?.message ?? '디자이너 목록 조회에 실패했습니다.')
  }

  return {
    code: data?.code ?? 200,
    message: data?.message ?? '디자이너 목록을 불러왔습니다.',
    designers: extractDesigners(data),
  }
}

export function writeDesignerListCache(designers: DesignerListItem[]) {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.setItem(
    DESIGNER_LIST_STORAGE_KEY,
    JSON.stringify(designers),
  )
}

export function readDesignerListCache(): DesignerListItem[] {
  if (typeof window === 'undefined') {
    return []
  }

  try {
    const raw = window.sessionStorage.getItem(DESIGNER_LIST_STORAGE_KEY)
    if (!raw) {
      return []
    }

    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) {
      return []
    }

    return parsed as DesignerListItem[]
  } catch {
    return []
  }
}
