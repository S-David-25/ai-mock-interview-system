/**
 * Base API Service Layer
 * Handles authentication header injection, JSON & FormData formatting, and centralized error handling.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
  }

  getToken() {
    return localStorage.getItem('ai_mock_token');
  }

  setToken(token) {
    if (token) {
      localStorage.setItem('ai_mock_token', token);
    } else {
      localStorage.removeItem('ai_mock_token');
    }
  }

  removeToken() {
    localStorage.removeItem('ai_mock_token');
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const token = this.getToken();

    const headers = {
      ...options.headers,
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // If body is NOT FormData, set JSON content-type
    if (options.body && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      let data;
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        if (response.status === 401) {
          // Token expired or invalid
          this.removeToken();
          window.dispatchEvent(new CustomEvent('auth:unauthorized'));
        }

        let errorMessage = 'An unexpected error occurred.';
        if (data && typeof data === 'object') {
          if (data.detail) {
            errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
          } else if (data.errors && Array.isArray(data.errors)) {
            errorMessage = data.errors.join('; ');
          } else if (data.message) {
            errorMessage = data.message;
          }
        }
        const error = new Error(errorMessage);
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    } catch (err) {
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        throw new Error('Unable to connect to the backend server. Please verify the backend is running.');
      }
      throw err;
    }
  }

  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  post(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'POST', body });
  }

  put(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'PUT', body });
  }

  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }
}

export const api = new ApiClient(API_BASE_URL);
