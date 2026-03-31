import { apiFetch } from '@/lib/api'

export type AiUpgradeRequest = {
  image: Blob
  deviceId?: string
}

export type AiUpgradeResponse = {
  code: number
  message: string
  success: boolean
  resultImageUrl: string | null
}

export async function postAiUpgrade({
  image,
  deviceId,
}: AiUpgradeRequest): Promise<AiUpgradeResponse> {
  const formData = new FormData()
  formData.append('image', image, 'camera-capture.png')

  if (deviceId) {
    formData.append('device_id', deviceId)
  }

  const response = await apiFetch('/camera/ai-upgrade/', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const data = (await response.json().catch(() => null)) as {
      message?: string
    } | null
    throw new Error(data?.message ?? 'AI 보정 요청에 실패했습니다.')
  }

  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.startsWith('image/')) {
    const blob = await response.blob()

    return {
      code: 200,
      message: 'AI 보정이 완료되었습니다.',
      success: true,
      resultImageUrl: URL.createObjectURL(blob),
    }
  }

  const data = (await response.json().catch(() => null)) as {
    code?: number
    message?: string
    success?: boolean
    result_image_url?: string
    result_url?: string
    image_url?: string
  } | null

  return {
    code: data?.code ?? 200,
    message: data?.message ?? 'AI 보정이 완료되었습니다.',
    success: data?.success ?? true,
    resultImageUrl:
      data?.result_image_url ?? data?.result_url ?? data?.image_url ?? null,
  }
}
