import { z } from 'zod'

const USER_ID_ONLY_REGEX = /^[A-Za-z0-9]+$/
const PASSWORD_ALLOWED_REGEX =
  /^[A-Za-z\d!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]+$/
const PASSWORD_HAS_LETTER_REGEX = /[A-Za-z]/
const PASSWORD_HAS_NUMBER_REGEX = /\d/
const PASSWORD_HAS_SPECIAL_REGEX = /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/
const AGE_REGEX = /^(?:[1-9]|[1-9][0-9]|1[01][0-9])$/

export const signupFormSchema = z
  .object({
    userId: z
      .string()
      .trim()
      .min(1, '아이디를 입력해주세요.')
      .min(6, '아이디는 6자 이상이어야 합니다.')
      .max(20, '아이디는 20자 이하여야 합니다.')
      .regex(
        USER_ID_ONLY_REGEX,
        '아이디는 영문 대/소문자와 숫자만 사용할 수 있습니다.',
      ),

    password: z
      .string()
      .min(1, '비밀번호를 입력해주세요.')
      .min(8, '비밀번호는 8자 이상이어야 합니다.')
      .max(16, '비밀번호는 16자 이하여야 합니다.')
      .regex(
        PASSWORD_ALLOWED_REGEX,
        '비밀번호는 영문, 숫자, 특수문자만 사용할 수 있습니다.',
      )
      .regex(
        PASSWORD_HAS_LETTER_REGEX,
        '비밀번호에는 영문이 최소 1개 이상 포함되어야 합니다.',
      )
      .regex(
        PASSWORD_HAS_NUMBER_REGEX,
        '비밀번호에는 숫자가 최소 1개 이상 포함되어야 합니다.',
      )
      .regex(
        PASSWORD_HAS_SPECIAL_REGEX,
        '비밀번호에는 특수문자가 최소 1개 이상 포함되어야 합니다.',
      ),

    passwordConfirm: z.string().min(1, '비밀번호 확인을 입력해주세요.'),

    age: z
      .string()
      .refine(
        (value) => value.trim() === '' || AGE_REGEX.test(value),
        '나이는 1~119 사이의 숫자만 입력할 수 있습니다.',
      ),

    gender: z.enum(['', 'M', 'F']),

    agreed: z.boolean(),
  })
  .superRefine((form, ctx) => {
    if (form.password !== form.passwordConfirm) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['passwordConfirm'],
        message: '비밀번호가 일치하지 않습니다.',
      })
    }

    if (!form.agreed) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ['agreed'],
        message: '이용약관 및 개인정보수집 동의가 필요합니다.',
      })
    }
  })

export type FormValues = z.infer<typeof signupFormSchema>

export type FormErrors = Partial<Record<keyof FormValues, string>>

export function validateField<K extends keyof FormValues>(
  key: K,
  form: FormValues,
): string | undefined {
  const result = signupFormSchema.safeParse(form)

  if (result.success) return undefined

  const issue = result.error.issues.find((item) => item.path[0] === key)
  return issue?.message
}

export function validateForm(form: FormValues): FormErrors {
  const result = signupFormSchema.safeParse(form)

  if (result.success) return {}

  const errors: FormErrors = {}

  for (const issue of result.error.issues) {
    const key = issue.path[0] as keyof FormValues | undefined
    if (!key) continue
    if (!errors[key]) {
      errors[key] = issue.message
    }
  }

  return errors
}
