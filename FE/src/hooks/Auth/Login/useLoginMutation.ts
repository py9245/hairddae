import { useMutation } from '@tanstack/react-query'
import { type LoginRequest, type LoginResponse, loginApi } from '@/lib/auth'

export function useLoginMutation() {
  return useMutation<LoginResponse, Error, LoginRequest>({
    mutationFn: loginApi,
  })
}
