import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';

// Mirrors the controller's launch gate (config.min_available_ram_gb / min_free_vram_mb).
export const RAM_FLOOR_GB = 7;
export const VRAM_FLOOR_MB = 7000;

// Above this multiple of a floor there is nothing worth saying.
const WARN_AT = 1.1;

function number(value) {
  const parsed = parseFloat(String(value ?? '').replace(/[^\d.]/g, ''));
  return Number.isFinite(parsed) ? parsed : null;
}

/** Free RAM and free VRAM against the floors that gate a launch. */
export function headroom(model) {
  const ram = Number.isFinite(Number(model?.available_ram_gb)) ? Number(model.available_ram_gb) : null;
  const total = number(model?.vram_total);
  const used = number(model?.vram_used);
  const vram = total !== null && used !== null ? total - used : null;
  return {
    ram,
    vram,
    ramOk: ram === null ? null : ram >= RAM_FLOOR_GB,
    vramOk: vram === null ? null : vram >= VRAM_FLOOR_MB,
    tight:
      (ram !== null && ram < RAM_FLOOR_GB * WARN_AT) ||
      (vram !== null && vram < VRAM_FLOOR_MB * WARN_AT),
  };
}

function Reading({ label, value, floor, unit, ok }) {
  return (
    <div className="reading">
      <span className="reading-label">{label}</span>
      <span className={`reading-value mono ${ok === false ? 'is-low' : ''}`}>
        {value === null ? '—' : `${value}${unit}`}
        <em>/ {floor}{unit}</em>
      </span>
    </div>
  );
}

/**
 * Hardware and runtime state, kept out of the library panel. It is ambient
 * chrome: a single chip in the title bar that opens a panel on demand, so the
 * numbers are one click away without occupying the workspace.
 */
export default function EngineStatus({ model, error, busy, onRefresh, onStop }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  const state = String(model?.status ?? 'offline').toLowerCase();
  const running = state === 'running';
  const installed = Boolean(model?.installed ?? model?.ready);
  const room = headroom(model);
  const message = error || model?.error;

  const tone = running ? 'busy' : state === 'error' || room.tight ? 'bad' : installed ? 'good' : 'idle';
  // Low memory is reported here rather than as a banner in the composer. The
  // chip already carries the tone; naming it keeps the dot from contradicting
  // a label that would otherwise still read "Ready".
  const label = running
    ? 'Rendering'
    : state === 'error'
      ? 'Worker stopped'
      : !installed
        ? 'Not installed'
        : room.tight
          ? 'Low memory'
          : 'Ready';

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event) => {
      if (!wrapRef.current?.contains(event.target)) setOpen(false);
    };
    const onKey = (event) => event.key === 'Escape' && setOpen(false);
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="engine-status" ref={wrapRef}>
      <button
        type="button"
        className={`engine-chip ${open ? 'is-open' : ''}`}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label="Engine and hardware status"
      >
        <span className={`dot dot-${tone} ${running ? 'pulsing' : ''}`} />
        {label}
      </button>

      {open && (
        <div className="engine-panel" role="dialog" aria-label="Engine details">
          <div className="engine-panel-head">
            <div>
              <h2>{model?.model_name || 'ACE-Step 1.5 Turbo'}</h2>
              <p>{model?.model_detail || 'local worker'}</p>
            </div>
            <button
              className="ghost-button"
              type="button"
              onClick={onRefresh}
              disabled={busy}
              aria-label="Refresh engine status"
            >
              <Icon name="refresh" size={15} />
            </button>
          </div>

          <div className="engine-panel-tags">
            <span className="tag"><Icon name="chip" size={12} /> {model?.device || 'GPU'}</span>
          </div>

          <div className="engine-readings">
            <Reading
              label="System RAM free"
              value={room.ram === null ? null : room.ram.toFixed(1)}
              floor={RAM_FLOOR_GB}
              unit=" GB"
              ok={room.ramOk}
            />
            <Reading
              label="GPU memory free"
              value={room.vram === null ? null : Math.round(room.vram)}
              floor={VRAM_FLOOR_MB}
              unit=" MB"
              ok={room.vramOk}
            />
          </div>

          {message && (
            <p className="notice notice-bad">
              <Icon name="alert" size={14} /> {message}
            </p>
          )}

          {running && (
            <button className="outline-button danger" type="button" onClick={onStop}>
              <Icon name="power" size={15} /> Stop worker
            </button>
          )}
        </div>
      )}
    </div>
  );
}
