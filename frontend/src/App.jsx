import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Composer from './components/Composer';
import EngineStatus, { headroom, RAM_FLOOR_GB, VRAM_FLOOR_MB } from './components/EngineStatus';
import PromptPalette from './components/PromptPalette';
import Activity from './components/Activity';
import Player from './components/Player';
import { api } from './lib/api';
import { isLive, isPlayable } from './lib/jobs';
import { useHeard } from './lib/heard';

const INITIAL_FORM = {
  prompt: '',
  lyrics: '',
  duration: 30,
  bpm: 110,
  key_scale: '',
  time_signature: '4/4',
  instrumental: true,
  seed: '',
  variations: 1,
};

function unwrap(payload, fallback) {
  if (Array.isArray(payload)) return payload;
  if (payload?.data !== undefined) return payload.data;
  return payload ?? fallback;
}

function normalizeModel(payload) {
  const value = unwrap(payload, {}) || {};
  const state = String(value.status ?? value.state ?? 'offline').toLowerCase();
  return { ...value, status: state };
}

function normalizeJobs(payload) {
  const value = unwrap(payload, []);
  if (Array.isArray(value)) return value;
  return value?.jobs ?? value?.items ?? [];
}

export default function App() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [model, setModel] = useState({ status: 'offline' });
  const [jobs, setJobs] = useState([]);
  const [modelLoading, setModelLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [modelError, setModelError] = useState('');
  const [jobsError, setJobsError] = useState('');
  const [formError, setFormError] = useState('');
  const [generating, setGenerating] = useState(false);
  const [pending, setPending] = useState({ cancel: null, retry: null });
  const [currentId, setCurrentId] = useState(null);
  // One level of undo, so loading a starter never silently discards typing.
  const [undoForm, setUndoForm] = useState(null);

  const autoLoaded = useRef(new Set());

  const refreshModel = useCallback(async () => {
    try {
      setModelError('');
      setModel(normalizeModel(await api.model()));
    } catch (error) {
      setModelError(error.message);
    } finally {
      setModelLoading(false);
    }
  }, []);

  const refreshJobs = useCallback(async () => {
    try {
      setJobsError('');
      setJobs(normalizeJobs(await api.jobs()));
    } catch (error) {
      setJobsError(error.message);
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshModel();
    const timer = window.setInterval(refreshModel, 4000);
    return () => window.clearInterval(timer);
  }, [refreshModel]);

  useEffect(() => {
    refreshJobs();
    const timer = window.setInterval(refreshJobs, 2000);
    return () => window.clearInterval(timer);
  }, [refreshJobs]);

  // A track that finishes loads itself into the dock, once, without autoplaying.
  useEffect(() => {
    const newest = jobs.find(isPlayable);
    if (!newest || autoLoaded.current.has(newest.id)) return;
    autoLoaded.current.add(newest.id);
    setCurrentId(newest.id);
  }, [jobs]);

  // The dock is permanent once a track exists; it is a transport, not a dialog.
  const current = useMemo(
    () => jobs.find((job) => job.id === currentId) ?? null,
    [jobs, currentId],
  );

  const room = headroom(model);
  const blocked = useMemo(() => {
    if (model?.installed === false) {
      return 'The ACE-Step runtime is not installed yet. Run setup.ps1 from the repository root.';
    }
    if (room.ramOk === false) {
      return `Only ${room.ram.toFixed(1)} GB system RAM is free; ${RAM_FLOOR_GB} GB is required before a run starts.`;
    }
    if (room.vramOk === false) {
      return `Only ${Math.round(room.vram)} MB GPU memory is free; ${VRAM_FLOOR_MB} MB is required before a run starts.`;
    }
    return '';
  }, [model, room]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setFormError('');
    const seed = String(form.seed).trim();
    try {
      await api.generate({
        prompt: form.prompt.trim(),
        lyrics: form.instrumental ? '' : form.lyrics.trim(),
        duration: Number(form.duration),
        bpm: form.bpm === '' ? null : Number(form.bpm),
        key_scale: form.key_scale,
        time_signature: form.time_signature || '4/4',
        instrumental: form.instrumental,
        seed: seed === '' ? null : Number(seed),
        variations: Number(form.variations) || 1,
      });
      setForm((value) => ({ ...value, prompt: '', lyrics: '' }));
      await refreshJobs();
    } catch (error) {
      setFormError(error.message);
    } finally {
      setGenerating(false);
    }
  }, [form, refreshJobs]);

  const handleCancel = useCallback(async (id) => {
    setPending((value) => ({ ...value, cancel: id }));
    try {
      await api.cancel(id);
      await refreshJobs();
    } catch (error) {
      setJobsError(error.message);
    } finally {
      setPending((value) => ({ ...value, cancel: null }));
    }
  }, [refreshJobs]);

  const handleRetry = useCallback(async (id) => {
    setPending((value) => ({ ...value, retry: id }));
    try {
      await api.retry(id);
      await refreshJobs();
    } catch (error) {
      setJobsError(error.message);
    } finally {
      setPending((value) => ({ ...value, retry: null }));
    }
  }, [refreshJobs]);

  const handleReuse = useCallback((job) => {
    setForm({
      prompt: job.prompt ?? '',
      lyrics: job.lyrics ?? '',
      duration: Number(job.duration) || 30,
      bpm: job.bpm ?? '',
      key_scale: job.key_scale ?? '',
      time_signature: job.time_signature || '4/4',
      instrumental: job.instrumental !== false,
      seed: job.seed ?? '',
      variations: 1,
    });
    document.getElementById('prompt')?.focus();
  }, []);

  const handleFavorite = useCallback(async (job) => {
    const next = !job.favorite;
    // Optimistic: the poll is up to 2s away and a toggle should feel instant.
    setJobs((current) => current.map((item) => (item.id === job.id ? { ...item, favorite: next } : item)));
    try {
      await api.favorite(job.id, next);
    } catch (error) {
      setJobsError(error.message);
    }
    await refreshJobs();
  }, [refreshJobs]);

  const handleDelete = useCallback(async (job) => {
    setJobs((current) => current.filter((item) => item.id !== job.id));
    if (job.id === currentId) setCurrentId(null);
    try {
      await api.remove(job.id);
    } catch (error) {
      setJobsError(error.message);
    }
    await refreshJobs();
  }, [refreshJobs, currentId]);

  const handleApplyStarter = useCallback((starter) => {
    setForm((current) => {
      setUndoForm(current);
      return {
        ...current,
        prompt: starter.prompt,
        bpm: starter.bpm ?? current.bpm,
        key_scale: starter.key ?? current.key_scale,
        duration: starter.duration ?? current.duration,
        instrumental: starter.instrumental ?? current.instrumental,
        lyrics: starter.instrumental ? '' : current.lyrics,
      };
    });
  }, []);

  const handleStopWorker = useCallback(async () => {
    try {
      await api.stopModel();
      await refreshModel();
    } catch (error) {
      setModelError(error.message);
    }
  }, [refreshModel]);

  const liveCount = jobs.filter(isLive).length;
  // The controller owns these ceilings; the composer follows them rather than
  // hardcoding limits the backend would reject.
  const maxDuration = Number(model?.max_duration_seconds) || 480;
  const maxVariations = Number(model?.max_variations) || 4;

  const { isUnheard, markHeard } = useHeard(jobs, !jobsLoading);

  return (
    <div className={`shell ${current ? 'has-player' : ''}`}>
      <header className="titlebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /><i /></span>
          <span className="brand-name">Fidget</span>
        </div>

        <div className="titlebar-meta">
          {liveCount > 0 && (
            <span className="tag tag-live"><span className="dot dot-busy pulsing" /> {liveCount} rendering</span>
          )}
          <EngineStatus
            model={model}
            error={modelError}
            busy={modelLoading}
            onRefresh={refreshModel}
            onStop={handleStopWorker}
          />
        </div>
      </header>

      <main className="stage">
        <PromptPalette
          prompt={form.prompt}
          onApplyStarter={handleApplyStarter}
          onSetPrompt={(value) => setForm((current) => ({ ...current, prompt: value }))}
          onUndo={() => {
            if (undoForm) setForm(undoForm);
            setUndoForm(null);
          }}
          canUndo={Boolean(undoForm)}
        />

        <div className="stage-main">
          <Composer
            form={form}
            setForm={setForm}
            onGenerate={handleGenerate}
            generating={generating}
            error={formError}
            blocked={blocked}
            maxDuration={maxDuration}
            maxVariations={maxVariations}
          />
        </div>

        <aside className="stage-rail">
          <Activity
            jobs={jobs}
            loading={jobsLoading}
            error={jobsError}
            currentId={current?.id ?? null}
            pending={pending}
            isUnheard={isUnheard}
            onPlay={(job) => setCurrentId(job.id)}
            onCancel={handleCancel}
            onRetry={handleRetry}
            onReuse={handleReuse}
            onFavorite={handleFavorite}
            onDelete={handleDelete}
          />
        </aside>
      </main>

      {current && <Player job={current} onReuse={handleReuse} onHeard={markHeard} />}
    </div>
  );
}
