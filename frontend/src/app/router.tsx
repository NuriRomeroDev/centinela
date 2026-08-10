import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '../components/shell/AppLayout'
import Dashboard from '../pages/Dashboard'
import Logs from '../pages/Logs'
import Sincronizaciones from '../pages/Sincronizaciones'
import Remediacion from '../pages/Remediacion'

export default function AppRouter() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="logs" element={<Logs />} />
        <Route path="syncs" element={<Sincronizaciones />} />
        <Route path="remediacion" element={<Remediacion />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
