import { useLocation } from 'react-router-dom'
import ThemeToggle from './ThemeToggle'

const TITLES: Record<string, [string, string]> = {
  '/': ['Dashboard de Control', 'Métricas en tiempo real de sincronizaciones y fallas'],
  '/logs': ['Logs de Errores', 'Catálogo de excepciones capturadas por el motor de ingestión'],
  '/syncs': ['Sincronizaciones', 'Control maestro de ejecuciones y archivos procesados'],
  '/remediacion': ['Historial de Remediación', 'Acciones manuales ejecutadas desde el tablero de control'],
}

export default function Header() {
  const { pathname } = useLocation()
  const [title, subtitle] = TITLES[pathname] ?? TITLES['/']
  return (
    <header className="header">
      <div>
        <h1 className="header-title">{title}</h1>
        <p className="header-subtitle">{subtitle}</p>
      </div>
      <div className="header-actions">
        <ThemeToggle />
        <div className="header-avatar" aria-label="Usuario MR">
          MR
        </div>
      </div>
    </header>
  )
}
