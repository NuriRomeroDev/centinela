import { useCallback, useEffect, useState } from 'react'
import { DEFAULT_THEME, THEME_STORAGE_KEY, type Theme } from '../app/theme'

function readStoredTheme(): Theme {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY)
  return stored === 'a' || stored === 'b' ? stored : DEFAULT_THEME
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(readStoredTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  }, [theme])

  const changeTheme = useCallback((next: Theme) => setTheme(next), [])

  return [theme, changeTheme]
}
