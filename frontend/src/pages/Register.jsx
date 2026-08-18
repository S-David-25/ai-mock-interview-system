import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { isValidEmail, validatePassword, validatePasswordMatch } from '../utils/validators';
import { Alert } from '../components/Alert';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { authService } from '../services/authService';

export function Register() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [formError, setFormError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Flow state: 'enter' | 'otp_sent' | 'verified'
  const [step, setStep] = useState('enter');
  const [otpSent, setOtpSent] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);

  const { register: registerContext, error: authError, clearError } = useAuth();
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
    clearError();

    if (!name.trim() || name.trim().length < 2) {
      setFormError('Please enter your full name (at least 2 characters).');
      return;
    }
    if (!email.trim() || !isValidEmail(email)) {
      setFormError('Please enter a valid email.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await authService.sendOtp({ name: name.trim(), email: email.trim() });
      if (res && res.status === 'ok') {
        setOtpSent(true);
        setStep('otp_sent');
        setResendCooldown(res.next_resend_seconds || 30);
      } else {
        setFormError('Failed to send OTP. Please try again later.');
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to send OTP.';
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const verifyOtp = async () => {
    setFormError('');
    if (!otp || otp.length < 4) {
      setFormError('Please enter the 6-digit OTP sent to your email.');
      return;
    }
    setIsSubmitting(true);
    try {
      await authService.verifyOtp({ email: email.trim(), otp: otp.trim() });
      setStep('verified');
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'OTP verification failed.';
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const resendOtp = async () => {
    if (resendCooldown > 0) return;
    setFormError('');
    setIsSubmitting(true);
    try {
      const res = await authService.sendOtp({ name: name.trim(), email: email.trim() });
      if (res && res.status === 'ok') {
        setResendCooldown(res.next_resend_seconds || 30);
      }
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to resend OTP.';
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateAccount = async (e) => {
    e.preventDefault();
    setFormError('');
    clearError();

    if (step !== 'verified') {
      setFormError('Please verify your email before creating an account.');
      return;
    }

    const pwCheck = validatePassword(password);
    if (!pwCheck.isValid) {
      setFormError(pwCheck.message);
      return;
    }
    const matchCheck = validatePasswordMatch(password, confirmPassword);
    if (!matchCheck.isValid) {
      setFormError(matchCheck.message);
      return;
    }

    setIsSubmitting(true);
    try {
      await registerContext(name.trim(), email.trim(), password, confirmPassword);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Registration failed.';
      setFormError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const errorMessage = formError || authError;

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-icon">🚀</div>
          <h2>Create Student Account</h2>
          <p>Master placement interviews with an AI-driven multi-modal coach.</p>
        </div>

        <Alert type="error" message={errorMessage} onDismiss={() => { setFormError(''); clearError(); }} />

        <form className="auth-form" noValidate onSubmit={step === 'verified' ? handleCreateAccount : (e)=>e.preventDefault()}>
          {step === 'enter' && (
            <>
              <div className="form-group">
                <label htmlFor="name">Full Name</label>
                <input
                  id="name"
                  type="text"
                  placeholder="Enter your full name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isSubmitting}
                  autoComplete="name"
                  required
                />
              </div>

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
            </>
          )}

          {step === 'otp_sent' && (
            <>
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
            </>
          )}

          {step === 'verified' && (
            <>
              <p>Email verified. Create your password.</p>

              <div className="form-group">
                <label htmlFor="password">Password (min 6 characters)</label>
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

              <button
                type="submit"
                className="btn btn-primary btn-block btn-lg"
                disabled={isSubmitting}
              >
                {isSubmitting ? <LoadingSpinner size="small" message="" /> : 'Create Account'}
              </button>
            </>
          )}
        </form>

        <div className="auth-footer">
          <p>
            Already registered?{' '}
            <Link to="/login" className="auth-link">
              Sign In here
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
