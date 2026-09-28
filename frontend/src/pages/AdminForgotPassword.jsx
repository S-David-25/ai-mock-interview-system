import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { adminService } from '../services/adminService';

export function AdminForgotPassword() {
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [step, setStep] = useState('email');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    let timer = null;
    if (resendCooldown > 0) {
      timer = setInterval(() => setResendCooldown((c) => Math.max(0, c - 1)), 1000);
    }
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const requestOtp = async () => {
    setFormError('');
    if (!email.trim()) {
      setFormError('Please enter your admin email.');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await adminService.sendForgotPasswordOtp({ email: email.trim() });
      setStep('otp');
      setResendCooldown(res.next_resend_seconds || 30);
    } catch (err) {
      setFormError(err.message || 'Unable to send reset OTP.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const verifyOtp = async () => {
    setFormError('');
    if (!otp || otp.length < 6) {
      setFormError('Please enter the 6-digit OTP.');
      return;
    }
    setIsSubmitting(true);
    try {
      await adminService.verifyForgotPasswordOtp({ email: email.trim(), otp: otp.trim() });
      setStep('reset');
    } catch (err) {
      setFormError(err.message || 'OTP verification failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setFormError('');
    if (!newPassword || newPassword.length < 6) {
      setFormError('Password must be at least 6 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setFormError('Passwords do not match.');
      return;
    }
    setIsSubmitting(true);
    try {
      await adminService.resetPassword({ email: email.trim(), new_password: newPassword, confirm_password: confirmPassword });
      window.location.href = '/admin/login';
    } catch (err) {
      setFormError(err.message || 'Password reset failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon">🔐</div>
          <h2>Admin Forgot Password</h2>
          <p>Reset access to the admin performance dashboard.</p>
        </div>

        <Alert type="error" message={formError} onDismiss={() => setFormError('')} />

        {step === 'email' && (
          <div className="auth-form">
            <div className="form-group">
              <label htmlFor="rec-email">Admin Email</label>
              <input id="rec-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="admin@company.com" />
            </div>
            <button className="btn btn-primary btn-block btn-lg" type="button" onClick={requestOtp} disabled={isSubmitting}>
              {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Send Reset OTP'}
            </button>
          </div>
        )}

        {step === 'otp' && (
          <div className="auth-form">
            <div className="form-group">
              <label htmlFor="reset-otp">Enter the 6-digit OTP</label>
              <input id="reset-otp" type="text" value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="123456" />
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn btn-primary" type="button" onClick={verifyOtp} disabled={isSubmitting}>
                {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Verify OTP'}
              </button>
              <button className="btn btn-link" type="button" onClick={requestOtp} disabled={isSubmitting || resendCooldown > 0}>
                {resendCooldown > 0 ? `Resend OTP in ${resendCooldown}s` : 'Resend OTP'}
              </button>
            </div>
          </div>
        )}

        {step === 'reset' && (
          <form onSubmit={handleReset} className="auth-form" noValidate>
            <div className="form-group">
              <label htmlFor="newPassword">New Password</label>
              <input id="newPassword" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <input id="confirmPassword" type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="••••••••" />
            </div>
            <button className="btn btn-primary btn-block btn-lg" type="submit" disabled={isSubmitting}>
              {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Reset Password'}
            </button>
          </form>
        )}

        <div className="auth-footer">
          <Link to="/admin/login" className="auth-link">Back to Admin Login</Link>
        </div>
      </div>
    </div>
  );
}
