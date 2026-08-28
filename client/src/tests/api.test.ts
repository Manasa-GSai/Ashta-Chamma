import { renderHook, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '@clerk/clerk-react';
import { useApiClient } from '../services/api';

// Hoisted by vitest — intercepts all imports of @clerk/clerk-react.
vi.mock('@clerk/clerk-react', () => ({
  useAuth: vi.fn(),
}));

describe('useApiClient', () => {
  const _originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = _originalFetch;
  });

  it('attaches a JWT Bearer token to the Authorization header', async () => {
    const mockToken = 'test-jwt-token';
    vi.mocked(useAuth).mockReturnValue({
      getToken: vi.fn().mockResolvedValue(mockToken),
    } as unknown as ReturnType<typeof useAuth>);

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: (): Promise<{ data: string }> => Promise.resolve({ data: 'ok' }),
    } as Response);
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const { result } = renderHook(() => useApiClient());

    await act(async () => {
      await result.current.apiFetch<{ data: string }>('/rooms');
    });

    expect(mockFetch).toHaveBeenCalledOnce();
    const [, requestInit] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Headers;
    expect(headers.get('Authorization')).toBe(`Bearer ${mockToken}`);
  });

  it('omits the Authorization header when Clerk returns no token', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getToken: vi.fn().mockResolvedValue(null),
    } as unknown as ReturnType<typeof useAuth>);

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: (): Promise<Record<string, unknown>> => Promise.resolve({}),
    } as Response);
    globalThis.fetch = mockFetch as unknown as typeof fetch;

    const { result } = renderHook(() => useApiClient());

    await act(async () => {
      await result.current.apiFetch<Record<string, unknown>>('/health');
    });

    const [, requestInit] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = requestInit.headers as Headers;
    expect(headers.get('Authorization')).toBeNull();
  });

  it('throws an ApiError with the response status on non-2xx responses', async () => {
    vi.mocked(useAuth).mockReturnValue({
      getToken: vi.fn().mockResolvedValue('token'),
    } as unknown as ReturnType<typeof useAuth>);

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      statusText: 'Unauthorized',
    } as Response) as unknown as typeof fetch;

    const { result } = renderHook(() => useApiClient());

    await act(async () => {
      await expect(result.current.apiFetch('/secure')).rejects.toMatchObject({
        status: 401,
      });
    });
  });
});
