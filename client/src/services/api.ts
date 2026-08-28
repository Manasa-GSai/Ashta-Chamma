import { useAuth } from '@clerk/clerk-react';
import { useCallback } from 'react';

// Base URL for all REST API calls. Falls back to /api for same-origin deployments.
const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? '/api';

export interface ApiError {
  message: string;
  status: number;
}

/**
 * Parses the response and throws a typed ApiError on non-2xx status codes.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = {
      message: `HTTP ${response.status}: ${response.statusText}`,
      status: response.status,
    };
    throw error;
  }
  return response.json() as Promise<T>;
}

/**
 * React hook that returns an authenticated fetch wrapper.
 * The wrapper retrieves a fresh Clerk JWT (automatic refresh before expiry)
 * and attaches it as a Bearer token on every request.
 *
 * Usage:
 *   const { apiFetch } = useApiClient();
 *   const data = await apiFetch<MyType>('/rooms', { method: 'POST', body: ... });
 */
export const useApiClient = (): {
  apiFetch: <T>(path: string, options?: RequestInit) => Promise<T>;
} => {
  const { getToken } = useAuth();

  const apiFetch = useCallback(
    async <T>(path: string, options: RequestInit = {}): Promise<T> => {
      // getToken() automatically refreshes the JWT when it is close to expiry.
      const token = await getToken();

      const headers = new Headers(options.headers as HeadersInit | undefined);
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      headers.set('Content-Type', 'application/json');

      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
      });

      return handleResponse<T>(response);
    },
    [getToken],
  );

  return { apiFetch };
};
