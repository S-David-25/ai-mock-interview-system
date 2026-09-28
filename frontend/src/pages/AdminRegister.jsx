import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { adminService } from '../services/adminService';

export function AdminRegister() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [step, setStep] = useState('enter');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [formError, setFormError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    let timer = null;
    if (resendCooldown > 0) {
      timer = setInterval(() => setResendCooldown((c) => Math.max(0, c - 1)), 1000);
    }
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const sendOtp = async () => {
    setFormError('');
    if (!name.trim() || name.trim().length < 2) {
      setFormError('Please enter your full name.');
      return;
    }
    if (!email.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setFormError('Please enter a valid email address.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await adminService.sendOtp({ name: name.trim(), email: email.trim() });
      setStep('otp');
      setResendCooldown(res.next_resend_seconds || 30);
    } catch (err) {
      setFormError(err.message || 'Failed to send OTP.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const verifyOtp = async () => {
    setFormError('');
    if (!otp || otp.length < 6) {
      setFormError('Please enter the 6-digit OTP sent to your email.');
      return;
    }

    setIsSubmitting(true);
    try {
      await adminService.verifyOtp({ email: email.trim(), otp: otp.trim() });
      setStep('password');
    } catch (err) {
      setFormError(err.message || 'OTP verification failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resendOtp = async () => {
    if (resendCooldown > 0) return;
    await sendOtp();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!password || password.length < 6) {
      setFormError('Password must be at least 6 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const data = await adminService.register({ name: name.trim(), email: email.trim(), password, confirm_password: confirmPassword });
      if (data.user?.role === 'admin') {
        navigate('/admin/dashboard', { replace: true });
      }
    } catch (err) {
      setFormError(err.message || 'Admin account creation failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon">🧑‍💼</div>
          <h2>Create Admin Account</h2>
          <p>Register a separate admin profile with OTP verification.</p>
        </div>

        <Alert type="error" message={formError} onDismiss={() => setFormError('')} />

        <form onSubmit={step === 'password' ? handleSubmit : (e) => e.preventDefault()} className="auth-form" noValidate>
          {step === 'enter' && (
            <>
              <div className="form-group">
                <label htmlFor="admin-name">Full Name</label>
                <input id="admin-name" type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Admin" />
              </div>
              <div className="form-group">
                <label htmlFor="admin-email">Admin Email</label>
                <input id="admin-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@company.com" />
              </div>
              <button type="button" className="btn btn-primary btn-block btn-lg" onClick={sendOtp} disabled={isSubmitting}>
                {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Send OTP'}
              </button>
            </>
          )}

          {step === 'otp' && (
            <>
              <p>Enter the 6-digit OTP sent to {email}.</p>
              <div className="form-group">
                <label htmlFor="otp">OTP</label>
                <input id="otp" type="text" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="123456" />
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button type="button" className="btn btn-primary" onClick={verifyOtp} disabled={isSubmitting}>
                  {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Verify OTP'}
                </button>
                <button type="button" className="btn btn-link" onClick={resendOtp} disabled={isSubmitting || resendCooldown > 0}>
                  {resendCooldown > 0 ? `Resend OTP in ${resendCooldown}s` : 'Resend OTP'}
                </button>
              </div>
            </>
          )}

          {step === 'password' && (
            <>
              <div className="form-group">
                <label htmlFor="admin-password">Password</label>
                <input id="admin-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
              </div>
              <div className="form-group">
                <label htmlFor="confirm-password">Confirm Password</label>
                <input id="confirm-password" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="••••••••" />
              </div>
              <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={isSubmitting}>
                {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Create Admin Account'}
              </button>
            </>
          )}
        </form>

        <div className="auth-footer">
          <p>
            Already have an admin account?{' '}
            <Link to="/admin/login" className="auth-link">Sign In</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
