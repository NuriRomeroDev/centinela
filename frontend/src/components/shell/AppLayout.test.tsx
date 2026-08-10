import { beforeEach, describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import AppLayout from './AppLayout'

const globalCss = readFileSync('src/styles/global.css', 'utf-8')

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppLayout />
    </MemoryRouter>,
  )
}

beforeEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
})

describe('AppLayout shell (R1)', () => {
  it('renders brand, 4 nav items and environment card', () => {
    renderAt('/')
    expect(screen.getByText('Centinela')).toBeInTheDocument()
    expect(screen.getByText('Control & Auditoría')).toBeInTheDocument()
    const nav = screen.getByRole('navigation')
    expect(within(nav).getByRole('link', { name: /Dashboard/ })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Logs de Errores/ })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Sincronizaciones/ })).toBeInTheDocument()
    expect(within(nav).getByRole('link', { name: /Remediación/ })).toBeInTheDocument()
    expect(screen.getByText('Ambiente')).toBeInTheDocument()
    expect(screen.getByText('On-Premise · Prod')).toBeInTheDocument()
    expect(screen.getByText('MR')).toBeInTheDocument()
  })

  it('renders fixed 248px sidebar and 64px header per mock', () => {
    const { container } = renderAt('/')
    expect(container.querySelector('.sidebar')).not.toBeNull()
    expect(container.querySelector('.header')).not.toBeNull()
    expect(globalCss).toMatch(/\.sidebar\s*\{[^}]*width:\s*248px/)
    expect(globalCss).toMatch(/\.header\s*\{[^}]*height:\s*64px/)
  })

  it('maps / to Dashboard with header title and subtitle per mock', () => {
    renderAt('/')
    expect(screen.getByRole('heading', { name: 'Dashboard de Control' })).toBeInTheDocument()
    expect(
      screen.getByText('Métricas en tiempo real de sincronizaciones y fallas'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Dashboard/ })).toHaveClass('sidebar-link--active')
  })

  it('navigates to /logs: route, header title and active nav update', async () => {
    const user = userEvent.setup()
    renderAt('/')
    await user.click(screen.getByRole('link', { name: /Logs de Errores/ }))
    expect(screen.getByRole('heading', { name: 'Logs de Errores' })).toBeInTheDocument()
    expect(
      screen.getByText('Catálogo de excepciones capturadas por el motor de ingestión'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Logs de Errores/ })).toHaveClass(
      'sidebar-link--active',
    )
    expect(screen.getByRole('link', { name: /Dashboard/ })).not.toHaveClass(
      'sidebar-link--active',
    )
  })
})

describe('Theme toggle (R2)', () => {
  it('defaults to Claro (palette A) with data-theme on the html element', () => {
    renderAt('/')
    expect(document.documentElement.dataset.theme).toBe('a')
    expect(screen.getByRole('button', { name: /Claro/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Oscuro/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('switches to Oscuro: data-theme=b, localStorage persisted, active segment flips', async () => {
    const user = userEvent.setup()
    renderAt('/')
    await user.click(screen.getByRole('button', { name: /Oscuro/ }))
    expect(document.documentElement.dataset.theme).toBe('b')
    expect(window.localStorage.getItem('centinela-theme')).toBe('b')
    expect(screen.getByRole('button', { name: /Oscuro/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Claro/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('respects a stored palette on mount', () => {
    window.localStorage.setItem('centinela-theme', 'b')
    renderAt('/')
    expect(document.documentElement.dataset.theme).toBe('b')
    expect(screen.getByRole('button', { name: /Oscuro/ })).toHaveAttribute('aria-pressed', 'true')
  })
})
