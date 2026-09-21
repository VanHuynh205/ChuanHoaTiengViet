import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function RoleGuard({
  children,
  role,
}: {
  children: React.ReactNode;
  role?: "admin" | "user";
}) {
  const { isAuthenticated, isBootstrapping, user } = useAuth();

  if (isBootstrapping) {
    return <div className="page-state">Đang kiểm tra phiên làm việc...</div>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (role && !user?.roles.includes(role)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
