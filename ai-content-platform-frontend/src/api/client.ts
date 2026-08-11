import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

type RetryConfig = InternalAxiosRequestConfig & { _retry?: boolean };

let refreshPromise: Promise<string | null> | null = null;

function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('user');
}

function redirectToLogin() {
  clearSession();
  if (!window.location.pathname.startsWith('/login')) {
    window.location.href = '/login';
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) return null;

  // Use bare axios so this call never re-enters the 401 interceptor.
  const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
    refresh_token: refreshToken,
  });
  const data = response.data?.data;
  const access = data?.access_token as string | undefined;
  if (!access) return null;

  localStorage.setItem('access_token', access);
  if (data.refresh_token) {
    localStorage.setItem('refresh_token', data.refresh_token);
  }
  return access;
}

function getSharedRefresh(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken()
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function ensureAccessToken(): Promise<string | null> {
  const existing = localStorage.getItem('access_token');
  if (existing) return existing;
  if (!localStorage.getItem('refresh_token')) return null;
  return getSharedRefresh();
}

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryConfig | undefined;
    const status = error.response?.status;
    const url = original?.url || '';

    if (status !== 401 || !original || original._retry) {
      return Promise.reject(error);
    }

    // Login / refresh failures should not attempt another refresh.
    if (url.includes('/auth/login') || url.includes('/auth/refresh')) {
      redirectToLogin();
      return Promise.reject(error);
    }

    original._retry = true;
    const access = await getSharedRefresh();
    if (!access) {
      redirectToLogin();
      return Promise.reject(error);
    }

    original.headers = original.headers || {};
    original.headers.Authorization = `Bearer ${access}`;
    return apiClient(original);
  }
);
