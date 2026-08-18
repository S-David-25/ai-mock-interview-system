import React, { createContext, useState, useEffect, useCallback } from 'react';
import { authService } from '../services/authService';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authService.getCurrentUser());
  const [token, setToken] = useState(() => localStorage.getItem('ai_mock_token'));
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Initialize session on mount
  useEffect(() => {
    async function loadUser() {
      const storedToken = localStorage.getItem('ai_mock_token');
      if (storedToken) {
        try {
          const userData = await authService.getMe();
          setUser(userData);
          setToken(storedToken);
        } catch (err) {
          console.warn('Session expired or invalid, logging out.');
          authService.logout();
          setUser(null);
          setToken(null);
        }
      }
      setIsLoading(false);
    }

    loadUser();

    // Listen to unauthorized global events
    const handleUnauthorized = () => {
      setUser(null);
      setToken(null);
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  const login = useCallback(async (email, password) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await authService.login({ email, password });
      setUser(response.user);
      setToken(response.access_token);
      return response.user;
    } catch (err) {
      setError(err.message || 'Login failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (name, email, password, confirmPassword) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await authService.register({
        name,
        email,
        password,
        confirm_password: confirmPassword,
      });
      setUser(response.user);
      setToken(response.access_token);
      return response.user;
    } catch (err) {
      setError(err.message || 'Registration failed');
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await authService.logout();
    } finally {
      setUser(null);
      setToken(null);
      setError(null);
      setIsLoading(false);
    }
  }, []);

  const clearError = () => setError(null);

  const value = {
    user,
    token,
    isAuthenticated: Boolean(user && token),
    isLoading,
    error,
    login,
    register,
    logout,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
