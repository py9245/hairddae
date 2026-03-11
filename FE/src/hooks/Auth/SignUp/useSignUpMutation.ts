import { useMutation } from '@tanstack/react-query'
import { signUpApi } from '@/lib/auth'

export function useSignUpMutation() {
  return useMutation({
    mutationFn: signUpApi,
  })
}
