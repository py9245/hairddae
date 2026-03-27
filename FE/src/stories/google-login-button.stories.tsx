import type { ComponentType } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from '@tanstack/react-router'
import { GoogleLoginButton } from '@/components/Auth/google-login-button'

function StoryRouterProvider({ Story }: { Story: ComponentType }) {
  const rootRoute = createRootRoute({
    component: Outlet,
  })

  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <Story />,
  })

  const router = createRouter({
    routeTree: rootRoute.addChildren([indexRoute]),
    history: createMemoryHistory({
      initialEntries: ['/'],
    }),
  })

  return <RouterProvider router={router} />
}

const meta = {
  title: 'UI/Button/GoogleLoginButton',
  component: GoogleLoginButton,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  decorators: [
    (Story) => {
      window.google = {
        accounts: {
          id: {
            initialize: () => undefined,
            prompt: () => undefined,
            renderButton: (parent) => {
              parent.innerHTML = ''

              const button = document.createElement('button')
              button.type = 'button'
              button.style.width = '243px'
              button.style.height = '40px'
              button.style.border = '1px solid #747775'
              button.style.borderRadius = '4px'
              button.style.background = '#ffffff'
              button.style.opacity = '0'
              parent.appendChild(button)
            },
          },
        },
      }

      return (
        <div className="w-[340px]">
          <StoryRouterProvider Story={Story} />
        </div>
      )
    },
  ],
} satisfies Meta<typeof GoogleLoginButton>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <GoogleLoginButton clientId="storybook-google-client-id" />,
}
