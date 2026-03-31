import { apiFetch } from '@/lib/api'

export type AiUpgradeRequest = {
  image: Blob
  hairId: number
  deviceId?: string
  promptOverride?: string
}

export type AiUpgradeResponse = {
  code: number
  message: string
  success: boolean
  jobId: string
  status: string
}

export async function postAiUpgrade({
  image,
  hairId,
  deviceId,
  promptOverride,
}: AiUpgradeRequest): Promise<AiUpgradeResponse> {
  const formData = new FormData()
  formData.append('image', image, 'camera-capture.png')
  formData.append('hair_id', String(hairId))

  if (deviceId) {
    formData.append('device_id', deviceId)
  }

  if (promptOverride) {
    formData.append('prompt_override', promptOverride)
  }

  const response = await apiFetch('/camera/ai-upgrade/', {
    method: 'POST',
    body: formData,
  })

  const data = (await response.json().catch(() => null)) as
    | {
        code?: number
        message?: string
        success?: boolean
        job_id?: string
        status?: string
      }
    | null

  if (!response.ok) {
    throw new Error(data?.message ?? 'AI 보정 요청에 실패했습니다.')
  }

  return {
    code: data?.code ?? 202,
    message: data?.message ?? 'AI 보정 작업이 접수되었습니다.',
    success: data?.success ?? true,
    jobId: data?.job_id ?? '',
    status: data?.status ?? 'PENDING',
  }
}
