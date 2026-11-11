const BASE = '/api/tf';

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    cache: 'no-store',
  });
  const text = await res.text();
  let body: unknown = null;
  try { body = text ? JSON.parse(text) : null; } catch { body = text; }
  if (!res.ok) {
    const msg =
      typeof body === 'object' && body && 'detail' in body
        ? String((body as Record<string, unknown>).detail)
        : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body as T;
}

export const api = {
  overview: () => http<import('./types').OverviewStats>('/stats'),
  listJobs: (qs: string) => http<import('./types').JobListResponse>(`/jobs${qs}`),
  getJob: (id: string) => http<import('./types').JobDetail>(`/jobs/${id}`),
  cancelJob: (id: string) =>
    http<import('./types').JobDetail>(`/jobs/${id}/cancel`, { method: 'POST' }),
};
