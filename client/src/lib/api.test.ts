import { describe, it, expect, vi, afterEach } from 'vitest';
import { apiFetch, ApiError } from './api';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('apiFetch', () => {
  it('returns parsed JSON on a successful response', async () => {
    const payload = { id: '1', name: 'test' };
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify(payload), { status: 200 }),
    );

    const result = await apiFetch<typeof payload>('/api/test');

    expect(result).toEqual(payload);
  });

  it('attaches Authorization header when token is provided', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 }),
    );

    await apiFetch('/api/secure', {}, 'my-token');

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const init = call[1] as RequestInit;
    expect((init.headers as Record<string, string>)['Authorization']).toBe('Bearer my-token');
  });

  it('does not attach Authorization header when token is omitted', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({}), { status: 200 }),
    );

    await apiFetch('/api/public');

    const call = vi.mocked(globalThis.fetch).mock.calls[0];
    const init = call[1] as RequestInit;
    expect((init.headers as Record<string, string>)['Authorization']).toBeUndefined();
  });

  it('throws ApiError with the response status on non-2xx response', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('Not Found', { status: 404, statusText: 'Not Found' }),
    );

    await expect(apiFetch('/api/missing')).rejects.toThrow(ApiError);
  });

  it('ApiError carries the correct status code', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response('Server Error', { status: 500, statusText: 'Internal Server Error' }),
    );

    let caught: ApiError | null = null;
    try {
      await apiFetch('/api/broken');
    } catch (e) {
      caught = e as ApiError;
    }

    expect(caught).not.toBeNull();
    expect(caught?.status).toBe(500);
    expect(caught?.name).toBe('ApiError');
  });
});
