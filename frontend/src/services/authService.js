import { api } from './api';

export const authService = {
  async sendOtp({ name, email }) {
    const data = await api.post('/api/auth/register/send-otp', { name, email });
    return data;
  },

  async verifyOtp({ email, otp }) {
    const data = await api.post('/api/auth/register/verify-otp', { email, otp });
    return data;
  },

  async register({ name, email, password, confirm_password }) {
    const data = await api.post('/api/auth/register', {
      name,
      email,
      password,
      confirm_password,
    });
    if (data.access_token) {
      api.setToken(data.access_token);
      localStorage.setItem('ai_mock_user', JSON.stringify(data.user));
    }
    return data;
  },

  async sendForgotPasswordOtp({ email }) {
    const data = await api.post('/api/auth/forgot-password/send-otp', { email });
    return data;
  },

  async verifyForgotPasswordOtp({ email, otp }) {
    const data = await api.post('/api/auth/forgot-password/verify-otp', { email, otp });
    return data;
  },

  async resetPassword({ email, new_password, confirm_password }) {
    const data = await api.post('/api/auth/forgot-password/reset', { email, new_password, confirm_password });
    return data;
  },

  async login({ email, password }) {
    const data = await api.post('/api/auth/login', {
      email,
      password,
    });
    if (data.access_token) {
      api.setToken(data.access_token);
      localStorage.setItem('ai_mock_user', JSON.stringify(data.user));
    }
    return data;
  },



  async getMe() {
    const user = await api.get('/api/auth/me');
    localStorage.setItem('ai_mock_user', JSON.stringify(user));
    return user;
  },

  async logout() {
    try {
      await api.post('/api/auth/logout');
    } catch (e) {
      // Ignore network error on logout
    } finally {
      api.removeToken();
      localStorage.removeItem('ai_mock_user');
    }
  },

  getCurrentUser() {
    const stored = localStorage.getItem('ai_mock_user');
    return stored ? JSON.parse(stored) : null;
  },

  isAuthenticated() {
    return Boolean(api.getToken());
  }
};
