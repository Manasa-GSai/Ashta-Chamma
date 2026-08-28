/**
 * Fetch wrapper for authenticated API requests.
 * All game API calls go through this module so auth headers and base URL
 * are applied consistently without coupling pages to raw fetch().
 */

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Thin fetch wrapper that attaches auth headers and throws ApiError on
 * non-2xx responses. Pass `token` for endpoints that require authentication.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const extraHeaders: Record<string, string> =
    token != null ? { Authorization: `Bearer ${token}` } : {};

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...extraHeaders,
      ...(options.headers as Record<string, string> | undefined),
    },
  });

  if (!response.ok) {
    throw new ApiError(
      `Request to ${path} failed: ${response.status} ${response.statusText}`,
      response.status,
    );
  }

  return response.json() as Promise<T>;
}
