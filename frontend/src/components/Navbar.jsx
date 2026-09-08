import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  if (!isAuthenticated) {
    return (
      <header className="navbar">
        <div className="navbar-container">
          <Link to="/" className="navbar-brand">
            <div className="logo-icon">🎯</div>
            <span className="brand-title">AI Mock Interview</span>
            <span className="brand-badge">Coach</span>
          </Link>
          <div className="navbar-links">
            <Link to="/login" className="btn btn-secondary btn-sm">Login</Link>
            <Link to="/register" className="btn btn-primary btn-sm">Get Started</Link>
          </div>
        </div>
      </header>
    );
  }

  const isDashboard = location.pathname === '/dashboard';
  const isSetup = location.pathname === '/setup';

  return (
    <header className="navbar">
      <div className="navbar-container">
        <Link to="/dashboard" className="navbar-brand">
          <div className="logo-icon">🎯</div>
          <span className="brand-title">AI Mock Interview</span>
          <span className="brand-badge">Student Coach</span>
        </Link>
        <div className="navbar-links">
          <Link
            to="/dashboard"
            className={`nav-link ${isDashboard ? 'active' : ''}`}
          >
            Dashboard
          </Link>
          <div className="user-profile-badge">
            <span className="user-avatar">{user?.name ? user.name.charAt(0).toUpperCase() : 'S'}</span>
            <span className="user-name">{user?.name || 'Student'}</span>
          </div>
          <button
            onClick={handleLogout}
            className="btn btn-outline btn-sm"
            title="Sign out of your account"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
