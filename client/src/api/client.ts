// API base URL — empty string routes through the Vite dev server proxy
const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? '';

export class ApiError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  if (!response.ok) {
    const message = await response
      .text()
      .catch(() => `HTTP ${response.status}`);
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<T>;
}

async function deleteRequest(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    const message = await response
      .text()
      .catch(() => `HTTP ${response.status}`);
    throw new ApiError(response.status, message);
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  delete: (path: string) => deleteRequest(path),
};
