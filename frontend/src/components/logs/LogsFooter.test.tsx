import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import LogsFooter from './LogsFooter'

function Harness() {
  const [page, setPage] = useState(1)
  return <LogsFooter total={38} page={page} pageSize={25} onPageChange={setPage} />
}

function countText(): string {
  const count = document.querySelector('.logs-footer-count') as HTMLElement
  return count.textContent ?? ''
}

describe('LogsFooter', () => {
  it('shows "Mostrando a-b de total" and page squares derived from total/page_size', () => {
    render(<LogsFooter total={38} page={1} pageSize={25} onPageChange={vi.fn()} />)
    expect(countText()).toMatch(/Mostrando 1[-–]25 de 38/)
    expect(screen.getByRole('button', { name: '1' })).toHaveClass('page-square--active')
    expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '3' })).not.toBeInTheDocument()
  })

  it('navigates between pages via the arrows and updates the active page', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: '›' }))
    expect(screen.getByRole('button', { name: '2' })).toHaveClass('page-square--active')
    expect(screen.getByRole('button', { name: '1' })).not.toHaveClass('page-square--active')
    await user.click(screen.getByRole('button', { name: '‹' }))
    expect(screen.getByRole('button', { name: '1' })).toHaveClass('page-square--active')
  })

  it('shows a single page after a server-filtered search', () => {
    render(<LogsFooter total={3} page={1} pageSize={25} onPageChange={vi.fn()} />)
    expect(countText()).toMatch(/Mostrando 1[-–]3 de 3/)
    expect(screen.getByRole('button', { name: '1' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument()
  })
})
