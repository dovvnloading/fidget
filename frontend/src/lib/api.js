const API_BASE = import.meta.env.VITE_API_BASE ?? '';

export function apiUrl(path) {
  return `${API_BASE}${path}`;
}

export function mediaUrl(path) {
  if (!path) return '';
  return /^https?:\/\//i.test(path) ? path : apiUrl(path);
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item?.msg || String(item)).join('; ')
      : payload.detail;
    throw new Error(payload.error || detail || `Request failed (${response.status})`);
  }
  return payload;
}

/** DELETE returns 204 with no body, so there is nothing to parse on success. */
async function remove(path) {
  const response = await fetch(apiUrl(path), { method: 'DELETE' });
  if (response.ok) return true;
  const payload = await response.json().catch(() => ({}));
  throw new Error(payload.detail || payload.error || `Request failed (${response.status})`);
}

export const api = {
  health: () => request('/api/health'),
  model: () => request('/api/model'),
  startModel: () => request('/api/model/start', { method: 'POST' }),
  stopModel: () => request('/api/model/stop', { method: 'POST' }),
  jobs: () => request('/api/jobs'),
  generate: (body) => request('/api/generate', { method: 'POST', body: JSON.stringify(body) }),
  cancel: (id) => request(`/api/jobs/${id}/cancel`, { method: 'POST' }),
  retry: (id) => request(`/api/jobs/${id}/retry`, { method: 'POST' }),
  favorite: (id, value) => request(`/api/jobs/${id}/favorite?favorite=${value ? 'true' : 'false'}`, { method: 'POST' }),
  remove: (id) => remove(`/api/jobs/${id}`),
  verification: () => request('/api/verification/latest'),
};
