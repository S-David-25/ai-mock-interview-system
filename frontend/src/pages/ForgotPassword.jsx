import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { isValidEmail, validatePassword, validatePasswordMatch } from '../utils/validators';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { authService } from '../services/authService';

export function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [step, setStep] = useState('enter'); // enter | otp_sent | verified
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [resendCooldown, setResendCooldown] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    let timer = null;
    if (resendCooldown > 0) {
      timer = setInterval(() => setResendCooldown((c) => Math.max(0, c - 1)), 1000);
    }
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const sendOtp = async () => {
    setError('');
    if (!email || !isValidEmail(email)) {
      setError('Please enter a valid email address.');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await authService.sendForgotPasswordOtp({ email: email.trim() });
      // Always show generic message
      if (res && res.status === 'ok') {
        setStep('otp_sent');
        setResendCooldown(res.next_resend_seconds || 30);
      } else {
        setStep('otp_sent');
        setResendCooldown(30);
      }
    } catch (err) {
      // Generic success message even on internal error to prevent enumeration
      setStep('otp_sent');
      setResendCooldown(30);
    } finally {
      setIsSubmitting(false);
    }
  };

  const verifyOtp = async () => {
    setError('');
    if (!otp || otp.length < 4) {
      setError('Please enter the 6-digit OTP sent to your email.');
      return;
    }
    setIsSubmitting(true);
    try {
      await authService.verifyForgotPasswordOtp({ email: email.trim(), otp: otp.trim() });
      setStep('verified');
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'OTP verification failed.';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resendOtp = async () => {
    if (resendCooldown > 0) return;
    setError('');
    setIsSubmitting(true);
    try {
      const res = await authService.sendForgotPasswordOtp({ email: email.trim() });
      setResendCooldown(res.next_resend_seconds || 30);
    } catch (err) {
      setError('Failed to resend OTP. Please try again later.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetPassword = async (e) => {
    e.preventDefault();
    setError('');

    if (step !== 'verified') {
      setError('Please verify your email OTP before resetting your password.');
      return;
    }

    const pwCheck = validatePassword(password);
    if (!pwCheck.isValid) {
      setError(pwCheck.message);
      return;
    }
    const matchCheck = validatePasswordMatch(password, confirmPassword);
    if (!matchCheck.isValid) {
      setError(matchCheck.message);
      return;
    }

    setIsSubmitting(true);
    try {
      await authService.resetPassword({ email: email.trim(), new_password: password, confirm_password: confirmPassword });
      // Show success and redirect to login
      navigate('/login', { replace: true });
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Password reset failed.';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon">🔐</div>
          <h2>Forgot Password?</h2>
          <p>Enter your registered email address to reset your password.</p>
        </div>

        <Alert type="error" message={error} onDismiss={() => setError('')} />

        {step === 'enter' && (
          <div className="auth-form">
            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <input
                id="email"
                type="email"
                placeholder="example@gmail.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSubmitting}
                autoComplete="email"
                required
              />
            </div>

            <button type="button" className="btn btn-primary btn-block btn-lg" onClick={sendOtp} disabled={isSubmitting}>
              {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Send OTP'}
            </button>

            <div className="auth-footer mt-3">
              <Link to="/login" className="auth-link">Back to Login</Link>
            </div>
          </div>
        )}

        {step === 'otp_sent' && (
          <div className="auth-form">
            <p>Enter the 6-digit OTP sent to {email}</p>
            <div className="form-group">
              <label htmlFor="otp">OTP</label>
              <input
                id="otp"
                type="text"
                placeholder="123456"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                disabled={isSubmitting}
                required
              />
            </div>

            <div className="d-flex" style={{ gap: '8px' }}>
              <button type="button" className="btn btn-primary" onClick={verifyOtp} disabled={isSubmitting}>
                {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Verify OTP'}
              </button>
              <button type="button" className="btn btn-link" onClick={resendOtp} disabled={isSubmitting || resendCooldown > 0}>
                {resendCooldown > 0 ? `Resend OTP in ${resendCooldown}s` : 'Resend OTP'}
              </button>
            </div>

            <div className="auth-footer mt-3">
              <Link to="/login" className="auth-link">Back to Login</Link>
            </div>
          </div>
        )}

        {step === 'verified' && (
          <form className="auth-form" onSubmit={resetPassword} noValidate>
            <p>Email verified. Enter your new password.</p>

            <div className="form-group">
              <label htmlFor="password">New Password</label>
              <input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                autoComplete="new-password"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <input
                id="confirmPassword"
                type="password"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={isSubmitting}
                autoComplete="new-password"
                required
              />
            </div>

            <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={isSubmitting}>
              {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Reset Password'}
            </button>

            <div className="auth-footer mt-3">
              <Link to="/login" className="auth-link">Back to Login</Link>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}
