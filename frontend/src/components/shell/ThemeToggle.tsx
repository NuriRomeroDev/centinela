import { useTheme } from '../../hooks/useTheme'

export default function ThemeToggle() {
  const [theme, changeTheme] = useTheme()
  return (
    <div className="theme-toggle" role="group" aria-label="Tema">
      <button
        type="button"
        className={`theme-toggle-option${theme === 'a' ? ' theme-toggle-option--active' : ''}`}
        aria-pressed={theme === 'a'}
        onClick={() => changeTheme('a')}
      >
        ☀ Claro
      </button>
      <button
        type="button"
        className={`theme-toggle-option${theme === 'b' ? ' theme-toggle-option--active' : ''}`}
        aria-pressed={theme === 'b'}
        onClick={() => changeTheme('b')}
      >
        ☾ Oscuro
      </button>
    </div>
  )
}
