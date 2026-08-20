import { useEffect, useRef } from 'react';
import Icon from './Icon';

const STYLES = [
  'dusty boom-bap',
  'ambient tape wash',
  'neo-soul ballad',
  'driving synthwave',
  'brushed jazz trio',
  'cinematic strings',
  'lo-fi bedroom pop',
  'industrial techno',
];

const KEYS = ['C Major', 'G Major', 'D Major', 'F Major', 'A Minor', 'E Minor', 'D Minor', 'B Minor'];
const METERS = [
  { value: '4/4', label: '4 / 4' },
  { value: '3/4', label: '3 / 4' },
  { value: '6/8', label: '6 / 8' },
  { value: '2/4', label: '2 / 4' },
];

/** Seconds below a minute stay in seconds; longer reads as m:ss. */
function lengthLabel(seconds) {
  const total = Math.round(Number(seconds) || 0);
  if (total < 60) return `${total}s`;
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function Field({ label, hint, htmlFor, children }) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={htmlFor}>
        {label}
        {hint && <span className="field-hint">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

export default function Composer({
  form,
  setForm,
  onGenerate,
  generating,
  error,
  blocked,
  maxDuration = 480,
  maxVariations = 4,
}) {
  const promptRef = useRef(null);
  const set = (key) => (value) => setForm((current) => ({ ...current, [key]: value }));
  const bind = (key) => (event) => set(key)(event.target.value);

  const ready = form.prompt.trim().length >= 3 && !generating && !blocked;

  // Ctrl + Enter submits from anywhere in the composer.
  useEffect(() => {
    const onKey = (event) => {
      if (event.ctrlKey && event.key === 'Enter' && ready) {
        event.preventDefault();
        onGenerate();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [ready, onGenerate]);

  const appendStyle = (style) => {
    setForm((current) => {
      const base = current.prompt.trim();
      if (base.toLowerCase().includes(style)) return current;
      return { ...current, prompt: base ? `${base}, ${style}` : style };
    });
    promptRef.current?.focus();
  };

  return (
    <section className="composer" aria-labelledby="composer-heading">
      <header className="composer-head">
        <div className="composer-title">
          <h1 id="composer-heading">What should it sound like?</h1>
          <p>Describe the feel, the room, the instruments. Detail helps more than genre labels.</p>
        </div>

        <div className="mode-switch" role="radiogroup" aria-label="Track type">
          <button
            type="button"
            role="radio"
            aria-checked={form.instrumental}
            className={form.instrumental ? 'is-on' : ''}
            onClick={() => set('instrumental')(true)}
          >
            Instrumental
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={!form.instrumental}
            className={!form.instrumental ? 'is-on' : ''}
            onClick={() => set('instrumental')(false)}
          >
            With vocals
          </button>
        </div>
      </header>

      <div className="composer-body">
        <Field label="Description" htmlFor="prompt">
          <div className="prompt-shell">
            <textarea
              id="prompt"
              ref={promptRef}
              className="prompt-input"
              value={form.prompt}
              onChange={bind('prompt')}
              placeholder="A slow, warm groove — rhodes chords, brushed drums, vinyl crackle underneath"
              rows={3}
              maxLength={1000}
            />
            <button
              className="send-button"
              type="button"
              onClick={onGenerate}
              disabled={!ready}
              aria-label={form.variations > 1 ? `Generate ${form.variations} takes` : 'Generate'}
              title={
                blocked ||
                (form.variations > 1
                  ? `Generate ${form.variations} takes  (Ctrl+Enter)`
                  : 'Generate  (Ctrl+Enter)')
              }
            >
              {generating ? <span className="spinner" /> : <Icon name="arrowUp" size={17} />}
            </button>
          </div>
          <div className="chip-row">
            {STYLES.map((style) => (
              <button key={style} type="button" className="chip" onClick={() => appendStyle(style)}>
                {style}
              </button>
            ))}
          </div>
        </Field>

        {!form.instrumental && (
          <Field label="Lyrics" hint="Use [verse] and [chorus] to mark sections" htmlFor="lyrics">
            <textarea
              id="lyrics"
              className="lyrics-input"
              value={form.lyrics}
              onChange={bind('lyrics')}
              placeholder={'[verse]\nSlow light on the kitchen floor\n\n[chorus]\n…'}
              rows={5}
              maxLength={4000}
            />
          </Field>
        )}

        <Field label="Length" hint={`up to ${lengthLabel(maxDuration)} on this profile`} htmlFor="duration">
          <div className="slider-row">
            <input
              id="duration"
              type="range"
              min="10"
              max={maxDuration}
              step="5"
              value={Math.min(form.duration, maxDuration)}
              onChange={(event) => set('duration')(Number(event.target.value))}
              style={{ '--fill': `${((form.duration - 10) / Math.max(1, maxDuration - 10)) * 100}%` }}
            />
            <output className="slider-value mono">{lengthLabel(form.duration)}</output>
          </div>
        </Field>

        <div className="control-grid">
          <Field label="Tempo" htmlFor="bpm">
            <div className="unit-input">
              <input
                id="bpm"
                type="number"
                min="30"
                max="300"
                value={form.bpm}
                onChange={(event) => set('bpm')(event.target.value)}
              />
              <span>BPM</span>
            </div>
          </Field>

          <Field label="Key" htmlFor="key">
            <select id="key" value={form.key_scale} onChange={bind('key_scale')}>
              <option value="">Any key</option>
              {KEYS.map((key) => <option key={key} value={key}>{key}</option>)}
            </select>
          </Field>

          <Field label="Meter" htmlFor="meter">
            <select id="meter" value={form.time_signature} onChange={bind('time_signature')}>
              {METERS.map((meter) => <option key={meter.value} value={meter.value}>{meter.label}</option>)}
            </select>
          </Field>

          <Field label="Seed" hint="Repeatable" htmlFor="seed">
            <div className="unit-input">
              <input
                id="seed"
                type="number"
                min="0"
                max="2147483647"
                value={form.seed}
                onChange={bind('seed')}
                placeholder="Random"
              />
              <button
                type="button"
                className="unit-button"
                title="Roll a new seed"
                onClick={() => set('seed')(String(Math.floor(Math.random() * 2147483647)))}
              >
                <Icon name="dice" size={15} />
              </button>
            </div>
          </Field>
        </div>

        <Field
          label="Takes"
          hint={form.variations > 1 ? 'rendered one after another' : 'a single take'}
        >
          <div className="take-picker" role="radiogroup" aria-label="Number of takes">
            {Array.from({ length: maxVariations }, (_, index) => index + 1).map((count) => (
              <button
                key={count}
                type="button"
                role="radio"
                aria-checked={form.variations === count}
                className={form.variations === count ? 'is-on' : ''}
                onClick={() => set('variations')(count)}
              >
                {count}
              </button>
            ))}
          </div>
        </Field>
      </div>

      {/* Only a real failure response gets a banner. Low memory is a passing
          condition, so it is carried by the title-bar chip and the send
          button's tooltip instead of a notice sitting in the workspace. */}
      {error && (
        <p className="notice notice-bad" role="alert">
          <Icon name="alert" size={15} /> {error}
        </p>
      )}
    </section>
  );
}
