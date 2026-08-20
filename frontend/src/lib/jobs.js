// The controller's JobRecord status enum, mirrored so the UI never invents states.
export const PENDING = new Set(['queued', 'starting']);
export const LIVE = new Set(['queued', 'starting', 'running']);

export function isLive(job) {
  return LIVE.has(status(job));
}

export function status(job) {
  return String(job?.status ?? 'queued').toLowerCase();
}

export function isPlayable(job) {
  return status(job) === 'succeeded' && Boolean(job?.result_url);
}

const TONES = {
  queued: { tone: 'idle', label: 'Queued' },
  starting: { tone: 'busy', label: 'Starting' },
  running: { tone: 'busy', label: 'Rendering' },
  succeeded: { tone: 'good', label: 'Ready' },
  failed: { tone: 'bad', label: 'Failed' },
  cancelled: { tone: 'muted', label: 'Cancelled' },
};

export function descriptor(job) {
  return TONES[status(job)] ?? { tone: 'idle', label: status(job) };
}

export function title(job) {
  const prompt = String(job?.prompt ?? '').trim();
  if (!prompt) return 'Untitled take';
  const firstClause = prompt.split(/[,.;\n]/)[0].trim();
  const text = firstClause.length >= 12 ? firstClause : prompt;
  return text.length > 64 ? `${text.slice(0, 63)}…` : text;
}

export function publicError(value) {
  const text = String(value || 'Generation failed. Try again.').replace(/\s+/g, ' ').trim();
  return text.length > 300 ? `${text.slice(0, 297)}…` : text;
}

export function clock(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

export function elapsedSince(iso) {
  if (!iso) return 0;
  const started = new Date(iso).getTime();
  if (Number.isNaN(started)) return 0;
  return Math.max(0, (Date.now() - started) / 1000);
}

export function relativeTime(iso) {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const seconds = Math.max(0, (Date.now() - then) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

export function megabytes(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return number >= 1024 ? `${(number / 1024).toFixed(1)} GB` : `${Math.round(number)} MB`;
}
