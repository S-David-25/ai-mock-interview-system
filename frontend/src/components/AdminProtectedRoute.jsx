import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { adminService } from '../services/adminService';
import { LoadingSpinner } from './LoadingSpinner';

export function AdminProtectedRoute({ children }) {
  const location = useLocation();
  const [ready, setReady] = React.useState(false);
  const [isAuthenticated, setIsAuthenticated] = React.useState(false);

  React.useEffect(() => {
    setIsAuthenticated(adminService.isAuthenticated());
    setReady(true);
  }, []);

  if (!ready) {
    return (
      <div style={{ minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <LoadingSpinner size="large" message="Checking admin access..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/admin/login" state={{ from: location }} replace />;
  }

  return children;
}
