import { useMemo, useState } from 'react'
import type { Gender } from '@/components/Auth/gender-select'
import {
  type FormErrors,
  validateField,
  validateForm,
} from '@/lib/Auth/SignUp/signupValidation'

export type FormValues = {
  userId: string
  password: string
  passwordConfirm: string
  birthDate: string
  gender: Gender
  agreed: boolean
}

type TouchedFields = Partial<Record<keyof FormValues, boolean>>

const initialValues: FormValues = {
  userId: '',
  password: '',
  passwordConfirm: '',
  birthDate: '',
  gender: null,
  agreed: false,
}

export function useSignUpForm() {
  const [values, setValues] = useState<FormValues>(initialValues)
  const [errors, setErrors] = useState<FormErrors>({})
  const [touchedFields, setTouchedFields] = useState<TouchedFields>({})

  function handleChange<K extends keyof FormValues>(
    key: K,
    value: FormValues[K],
  ) {
    setValues((prev) => {
      const nextValues = {
        ...prev,
        [key]: value,
      }

      setErrors((prevErrors) => ({
        ...prevErrors,
        ...(touchedFields[key]
          ? {
              [key]: validateField(key, nextValues),
            }
          : {}),
        ...(key === 'password' && touchedFields.passwordConfirm
          ? {
              passwordConfirm: validateField('passwordConfirm', nextValues),
            }
          : {}),
      }))

      return nextValues
    })

    setTouchedFields((prev) => ({
      ...prev,
      [key]: true,
    }))
  }

  function handleBlur<K extends keyof FormValues>(key: K) {
    const nextTouchedFields = {
      ...touchedFields,
      [key]: true,
    }
    const message = validateField(key, values)

    setTouchedFields(nextTouchedFields)

    setErrors((prev) => ({
      ...prev,
      [key]: message,
      ...(key === 'password' && nextTouchedFields.passwordConfirm
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
    setTouchedFields({
      userId: true,
      password: true,
      passwordConfirm: true,
      birthDate: true,
      gender: true,
      agreed: true,
    })
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
