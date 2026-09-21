import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { RoleGuard } from "./components/RoleGuard";
import { AdminAccountsPage } from "./pages/AdminAccountsPage";
import { AdminDictionaryPage } from "./pages/AdminDictionaryPage";
import { AdminModerationPage } from "./pages/AdminModerationPage";
import { HistoryPage } from "./pages/HistoryPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { WorkspacePage } from "./pages/WorkspacePage";

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/"
              element={
                <RoleGuard>
                  <AppShell />
                </RoleGuard>
              }
            >
              <Route index element={<WorkspacePage />} />
              <Route path="dictionary" element={<AdminDictionaryPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="admin" element={<Navigate to="/admin/moderation" replace />} />
              <Route
                path="admin/accounts"
                element={
                  <RoleGuard role="admin">
                    <AdminAccountsPage />
                  </RoleGuard>
                }
              />
              <Route
                path="admin/moderation"
                element={
                  <RoleGuard role="admin">
                    <AdminModerationPage />
                  </RoleGuard>
                }
              />
              <Route
                path="admin/dictionary"
                element={<Navigate to="/dictionary" replace />}
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
