import { BrowserRouter, Routes, Route } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Onboarding from './pages/Onboarding'
import CommandDeck from './pages/CommandDeck'
import OntologyExplorer from './pages/OntologyExplorer'
import Investigation from './pages/Investigation'
import AutonomyConsole from './pages/AutonomyConsole'
import Provenance from './pages/Provenance'
import RiskDashboard from './pages/RiskDashboard'
import Inventory from './pages/Inventory'
import PurpleTeam from './pages/PurpleTeam'
import Reports from './pages/Reports'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<CommandDeck />} />
          <Route path="onboarding" element={<Onboarding />} />
          <Route path="ontology" element={<OntologyExplorer />} />
          <Route path="investigation" element={<Investigation />} />
          <Route path="autonomy" element={<AutonomyConsole />} />
          <Route path="provenance" element={<Provenance />} />
          <Route path="risk" element={<RiskDashboard />} />
          <Route path="inventory" element={<Inventory />} />
          <Route path="purple-team" element={<PurpleTeam />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
