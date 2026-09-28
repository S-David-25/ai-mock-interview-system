import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { adminService } from '../services/adminService';

const THEME_STORAGE_KEY = 'ai_mock_theme';

function ThemeToggle() {
  const [theme, setTheme] = React.useState(() => {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  return (
    <button
      type="button"
      className="btn btn-outline btn-sm"
      onClick={() => setTheme((current) => (current === 'dark' ? 'light' : 'dark'))}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      title={`Current theme: ${theme}`}
    >
      {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
    </button>
  );
}

export function Navbar() {
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const isAdminAuthenticated = adminService.isAuthenticated();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const handleAdminLogout = async () => {
    await adminService.logout();
    navigate('/admin/login');
  };

  if (isAdminAuthenticated) {
    return (
      <header className="navbar">
        <div className="navbar-container">
          <Link to="/admin/dashboard" className="navbar-brand">
            <div className="logo-icon">🎯</div>
            <span className="brand-title">AI Mock Interview</span>
            <span className="brand-badge">Admin</span>
          </Link>
          <div className="navbar-links">
            <ThemeToggle />
            <button onClick={handleAdminLogout} className="btn btn-outline btn-sm" title="Sign out of your admin account">
              Logout
            </button>
          </div>
        </div>
      </header>
    );
  }

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
            <ThemeToggle />
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
          <ThemeToggle />
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
