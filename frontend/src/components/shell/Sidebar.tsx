import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: '◧', end: true },
  { to: '/logs', label: 'Logs de Errores', icon: '⚠' },
  { to: '/syncs', label: 'Sincronizaciones', icon: '⇄' },
  { to: '/remediacion', label: 'Remediación', icon: '✓' },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">C</div>
        <div>
          <div className="sidebar-name">Centinela</div>
          <div className="sidebar-sub">Control &amp; Auditoría</div>
        </div>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `sidebar-link${isActive ? ' sidebar-link--active' : ''}`
            }
          >
            <span className="sidebar-icon">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-env">
        <div className="sidebar-env-label">Ambiente</div>
        <div className="sidebar-env-value">
          <span className="sidebar-env-dot" />
          On-Premise · Prod
        </div>
      </div>
    </aside>
  )
}
