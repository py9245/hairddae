import { mutationOptions } from '@tanstack/react-query'

import { auth } from '@/lib/auth'

export const logoutMutationOptions = () =>
  mutationOptions({
    mutationFn: async () => await auth.logout(),
    onSuccess: () => {
      window.location.reload()
    },
  })
