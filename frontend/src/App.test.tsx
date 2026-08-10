import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App scaffold', () => {
  it('renders the Centinela brand', () => {
    render(<App />)
    expect(screen.getByText('Centinela')).toBeInTheDocument()
  })
})
