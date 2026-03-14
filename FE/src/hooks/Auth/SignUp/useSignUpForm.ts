import { useMemo, useState } from 'react'
import {
  type FormErrors,
  type FormValues,
  validateField,
  validateForm,
} from '@/lib/Auth/SignUp/signupValidation'

const initialValues: FormValues = {
  userId: '',
  password: '',
  passwordConfirm: '',
  birthDate: '',
  gender: '',
  agreed: false,
}

export function useSignUpForm() {
  const [values, setValues] = useState<FormValues>(initialValues)
  const [errors, setErrors] = useState<FormErrors>({})

  function handleChange<K extends keyof FormValues>(
    key: K,
    value: FormValues[K],
  ) {
    setValues((prev) => ({
      ...prev,
      [key]: value,
    }))
  }

  function handleBlur<K extends keyof FormValues>(key: K) {
    const message = validateField(key, values)

    setErrors((prev) => ({
      ...prev,
      [key]: message,
      ...(key === 'password' && values.passwordConfirm
        ? {
            passwordConfirm: validateField('passwordConfirm', values),
          }
        : {}),
    }))
  }

  const formErrors = useMemo(() => validateForm(values), [values])

  const isFormValid = useMemo(() => {
    return (
      values.userId.trim() !== '' &&
      values.password !== '' &&
      values.passwordConfirm !== '' &&
      values.agreed &&
      Object.values(formErrors).every((error) => !error)
    )
  }, [values, formErrors])

  function handleSubmit(
    e: React.FormEvent<HTMLFormElement>,
    onValidSubmit?: (formValues: FormValues) => void,
  ) {
    e.preventDefault()

    const nextErrors = validateForm(values)
    setErrors(nextErrors)

    const hasError = Object.values(nextErrors).some(Boolean)
    if (hasError) return

    onValidSubmit?.(values)
  }

  return {
    values,
    errors,
    isFormValid,
    handleChange,
    handleBlur,
    handleSubmit,
  }
}
