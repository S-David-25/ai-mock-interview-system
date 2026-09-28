import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { adminService } from '../services/adminService';

export function AdminLogin() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || '/admin/dashboard';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!email.trim()) {
      setFormError('Please enter your admin email address.');
      return;
    }
    if (!password) {
      setFormError('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      const data = await adminService.login({ email: email.trim(), password });
      if (data.user?.role === 'admin') {
        navigate(from, { replace: true });
      } else {
        setFormError('Admin account required.');
      }
    } catch (err) {
      setFormError(err?.message || 'Admin login failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon">🛡️</div>
          <h2>Admin Login</h2>
          <p>Sign in to access the candidate performance dashboard.</p>
        </div>

        <Alert type="error" message={formError} onDismiss={() => setFormError('')} />

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <div className="form-group">
            <label htmlFor="admin-email">Admin Email</label>
            <input id="admin-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} disabled={isSubmitting} placeholder="admin@company.com" />
          </div>

          <div className="form-group">
            <label htmlFor="admin-password">Password</label>
            <input id="admin-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} disabled={isSubmitting} placeholder="••••••••" />
          </div>

          <button className="btn btn-primary btn-block btn-lg" type="submit" disabled={isSubmitting}>
            {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Sign In as Admin'}
          </button>
        </form>

        <div className="auth-footer" style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
          <Link to="/admin/register" className="auth-link">Create Admin Account</Link>
          <Link to="/admin/forgot-password" className="auth-link">Forgot Password?</Link>
        </div>
      </div>
    </div>
  );
}
