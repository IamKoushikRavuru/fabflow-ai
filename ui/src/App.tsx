import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MainLayout } from '@/layouts/MainLayout';
import { LiveSyncProvider } from '@/context/LiveSyncContext';
import { AuthProvider } from '@/context/AuthContext';
import { NotificationProvider } from '@/context/NotificationContext';
import DashboardPage from '@/features/dashboard/DashboardPage';
import FinancePage from '@/features/finance/FinancePage';
import SimulationPage from '@/features/simulation/SimulationPage';
import AnalyticsPage from '@/features/analytics/AnalyticsPage';
import ReportsPage from '@/features/reports/ReportsPage';
import SettingsPage from '@/features/settings/SettingsPage';

function App() {
  return (
    <AuthProvider>
      <NotificationProvider>
        <LiveSyncProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<MainLayout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/explore" element={<FinancePage />} />
                <Route path="/simulate" element={<SimulationPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </LiveSyncProvider>
      </NotificationProvider>
    </AuthProvider>
  );
}

export default App;
