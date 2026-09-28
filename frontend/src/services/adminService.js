import { api } from './api';

const ADMIN_TOKEN_KEY = 'ai_mock_admin_token';
const ADMIN_USER_KEY = 'ai_mock_admin_user';

export const adminService = {
  setSession(token, user) {
    if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token);
    else localStorage.removeItem(ADMIN_TOKEN_KEY);
    if (user) localStorage.setItem(ADMIN_USER_KEY, JSON.stringify(user));
    else localStorage.removeItem(ADMIN_USER_KEY);
  },

  clearSession() {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    localStorage.removeItem(ADMIN_USER_KEY);
  },

  getCurrentUser() {
    const raw = localStorage.getItem(ADMIN_USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      this.clearSession();
      return null;
    }
  },

  isAuthenticated() {
    return Boolean(localStorage.getItem(ADMIN_TOKEN_KEY) && this.getCurrentUser()?.role === 'admin');
  },

  async sendOtp({ name, email }) {
    return api.post('/api/admin/send-otp', { name, email });
  },

  async verifyOtp({ email, otp }) {
    return api.post('/api/admin/verify-otp', { email, otp });
  },

  async register({ name, email, password, confirm_password }) {
    const data = await api.post('/api/admin/register', { name, email, password, confirm_password });
    if (data.access_token) {
      this.setSession(data.access_token, data.user);
      api.setToken(data.access_token, 'admin');
    }
    return data;
  },

  async login({ email, password }) {
    const data = await api.post('/api/admin/login', { email, password });
    if (data.access_token) {
      this.setSession(data.access_token, data.user);
      api.setToken(data.access_token, 'admin');
    }
    return data;
  },

  async sendForgotPasswordOtp({ email }) {
    return api.post('/api/admin/forgot-password/send-otp', { email });
  },

  async verifyForgotPasswordOtp({ email, otp }) {
    return api.post('/api/admin/forgot-password/verify-otp', { email, otp });
  },

  async resetPassword({ email, new_password, confirm_password }) {
    return api.post('/api/admin/forgot-password/reset', { email, new_password, confirm_password });
  },

  async getDashboard() {
    return api.get('/api/admin/dashboard');
  },

  async getCandidates({ page = 1, limit = 20, search = '' } = {}) {
    const query = new URLSearchParams({ page: String(page), limit: String(limit) });
    if (search) query.set('search', search);
    return api.get(`/api/admin/candidates?${query.toString()}`);
  },

  async getCandidateDetail(candidateId) {
    return api.get(`/api/admin/candidates/${candidateId}`);
  },

  async getCandidateInterviews(candidateId) {
    return api.get(`/api/admin/candidates/${candidateId}/interviews`);
  },

  async getInterviewDetail(interviewId) {
    return api.get(`/api/admin/interviews/${interviewId}`);
  },

  async getInterviewQuestions(interviewId) {
    return api.get(`/api/admin/interviews/${interviewId}/questions`);
  },

  async getCandidateComparison(candidateId) {
    return api.get(`/api/admin/candidates/${candidateId}/comparison`);
  },

  async logout() {
    try {
      await api.post('/api/admin/logout');
    } catch (e) {
      // Ignore
    } finally {
      this.clearSession();
    }
  },
};
