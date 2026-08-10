import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

export default function AppLayout() {
  return (
    <div className="shell">
      <Sidebar />
      <div className="shell-main">
        <Header />
        <main className="shell-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
