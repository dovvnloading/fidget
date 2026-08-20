import { useEffect, useState } from 'react';
import Icon from './Icon';
import { clock, descriptor, elapsedSince, isLive, isPlayable, publicError, relativeTime, status, title } from '../lib/jobs';

function useTicker(active) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active) return undefined;
    const timer = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
}

function RenderBars() {
  return (
    <div className="render-bars" aria-hidden="true">
      {Array.from({ length: 28 }, (_, index) => (
        <i key={index} style={{ animationDelay: `${(index % 9) * 0.11}s` }} />
      ))}
    </div>
  );
}

function LiveJob({ job, onCancel, cancelling }) {
  useTicker(true);
  const state = status(job);
  const queued = state === 'queued' || state === 'starting';
  const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
  const elapsed = elapsedSince(job.created_at);
  const batched = Number(job.batch_size) > 1;

  return (
    <article className="live-job">
      <div className="live-head">
        <span className="live-state">
          <span className="dot dot-busy pulsing" />
          {queued ? 'Waiting for the worker' : 'Rendering'}
          {batched && (
            <span className="live-take">
              {job.batch_index}/{job.batch_size}
            </span>
          )}
        </span>
        <span className="live-elapsed mono">{clock(elapsed)}</span>
      </div>

      <h3 className="live-title">{title(job)}</h3>

      <RenderBars />

      <div className="live-progress">
        <div className="progress-track">
          <span className="progress-fill" style={{ width: `${Math.max(2, progress)}%` }} />
        </div>
        <div className="live-meta">
          <span>{job.message || 'Preparing…'}</span>
          <span className="mono">{Math.round(progress)}%</span>
        </div>
      </div>

      <div className="live-foot">
        <span className="live-spec mono">
          {job.duration}s · {job.instrumental ? 'instrumental' : 'vocals'}{job.bpm ? ` · ${job.bpm} BPM` : ''}
        </span>
        <button className="outline-button danger small" type="button" onClick={() => onCancel(job.id)} disabled={cancelling}>
          <Icon name="close" size={13} /> {cancelling ? 'Cancelling…' : 'Cancel'}
        </button>
      </div>
    </article>
  );
}

/** Queued takes waiting behind the running one; compact by design. */
function QueuedRow({ job, onCancel, cancelling }) {
  const batched = Number(job.batch_size) > 1;
  return (
    <div className="queued-row">
      <span className="dot dot-idle" />
      <span className="queued-label">
        {batched ? `Take ${job.batch_index} of ${job.batch_size}` : 'Queued'}
      </span>
      <button
        className="ghost-button"
        type="button"
        onClick={() => onCancel(job.id)}
        disabled={cancelling}
        aria-label="Cancel this take"
        title="Cancel this take"
      >
        <Icon name="close" size={13} />
      </button>
    </div>
  );
}

function HistoryRow({ job, active, unheard, onPlay, onRetry, onReuse, onFavorite, onDelete, retrying }) {
  const state = status(job);
  const info = descriptor(job);
  const playable = isPlayable(job);
  const failed = state === 'failed';
  const cancelled = state === 'cancelled';
  // Deleting is irreversible, so the button asks once rather than opening a
  // modal. It reverts on blur or after a few seconds.
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!confirming) return undefined;
    const timer = window.setTimeout(() => setConfirming(false), 3500);
    return () => window.clearTimeout(timer);
  }, [confirming]);

  return (
    <article
      className={`history-row tone-${info.tone} ${unheard ? 'is-unheard' : ''} ${active ? 'is-active' : ''}`}
    >
      <button
        className="history-main"
        type="button"
        onClick={() => playable && onPlay(job)}
        disabled={!playable}
        aria-label={playable ? `Play ${title(job)}` : title(job)}
      >
        <span className="history-glyph">
          {playable ? <Icon name={active ? 'wave' : 'play'} size={14} /> : <span className={`dot dot-${info.tone}`} />}
        </span>
        <span className="history-copy">
          <span className="history-title">{title(job)}</span>
          <span className="history-sub mono">
            {job.duration}s · {job.instrumental ? 'instrumental' : 'vocals'} · {relativeTime(job.created_at)}
          </span>
        </span>
      </button>

      <div className="history-actions">
        {(failed || cancelled) && (
          <button className="ghost-button" type="button" onClick={() => onRetry(job.id)} disabled={retrying} title="Run this again">
            <Icon name="refresh" size={14} />
          </button>
        )}
        <button className="ghost-button" type="button" onClick={() => onReuse(job)} title="Load these settings into the composer">
          <Icon name="copy" size={14} />
        </button>
        {playable && (
          <button
            className={`ghost-button ${job.favorite ? 'is-favorite' : ''}`}
            type="button"
            onClick={() => onFavorite(job)}
            aria-pressed={Boolean(job.favorite)}
            title={job.favorite ? 'Remove from favourites' : 'Add to favourites'}
          >
            <Icon name="thumbUp" size={14} />
          </button>
        )}
        <button
          className={`ghost-button ${confirming ? 'is-danger' : ''}`}
          type="button"
          onClick={() => (confirming ? onDelete(job) : setConfirming(true))}
          onBlur={() => setConfirming(false)}
          title={confirming ? 'Click again to delete for good' : 'Delete this take'}
          aria-label={confirming ? 'Confirm delete' : 'Delete this take'}
        >
          <Icon name={confirming ? 'trash' : 'thumbDown'} size={14} />
        </button>
      </div>

      {failed && job.error && (
        <p className="history-error">
          <Icon name="alert" size={13} /> {publicError(job.error)}
        </p>
      )}
    </article>
  );
}

export default function Activity({
  jobs,
  loading,
  error,
  currentId,
  isUnheard,
  onPlay,
  onCancel,
  onRetry,
  onReuse,
  onFavorite,
  onDelete,
  pending,
}) {
  const [onlyFavorites, setOnlyFavorites] = useState(false);

  const live = jobs.filter(isLive);
  const finished = jobs.filter((job) => !isLive(job));
  const past = onlyFavorites ? finished.filter((job) => job.favorite) : finished;
  const favoriteCount = finished.filter((job) => job.favorite).length;
  // Only one take can be on the GPU, so the rest are shown as a compact queue
  // rather than a stack of full-size cards.
  const active = live.filter((job) => status(job) !== 'queued');
  const waiting = live.filter((job) => status(job) === 'queued');

  return (
    <section className="activity" aria-labelledby="activity-heading">
      <div className="activity-pinned">
        <div className="library-head">
          <h2 id="activity-heading">Library</h2>
          {favoriteCount > 0 && (
            <button
              type="button"
              className={`filter-toggle ${onlyFavorites ? 'is-on' : ''}`}
              onClick={() => setOnlyFavorites((value) => !value)}
              aria-pressed={onlyFavorites}
              title="Show favourites only"
            >
              <Icon name="thumbUp" size={13} /> {favoriteCount}
            </button>
          )}
        </div>

        {error && (
          <p className="notice notice-bad">
            <Icon name="alert" size={14} /> {error}
          </p>
        )}

        {active.map((job) => (
          <LiveJob key={job.id} job={job} onCancel={onCancel} cancelling={pending.cancel === job.id} />
        ))}

        {waiting.length > 0 && (
          <div className="queued-list">
            {waiting.map((job) => (
              <QueuedRow
                key={job.id}
                job={job}
                onCancel={onCancel}
                cancelling={pending.cancel === job.id}
              />
            ))}
          </div>
        )}
      </div>

      <div className="activity-scroll">
        {past.length > 0 && (
          <div className="history-group">
            <div className="history-list">
              {past.map((job) => (
                <HistoryRow
                  key={job.id}
                  job={job}
                  active={job.id === currentId}
                  unheard={isUnheard?.(job) ?? false}
                  onPlay={onPlay}
                  onRetry={onRetry}
                  onReuse={onReuse}
                  onFavorite={onFavorite}
                  onDelete={onDelete}
                  retrying={pending.retry === job.id}
                />
              ))}
            </div>
          </div>
        )}

        {onlyFavorites && past.length === 0 && finished.length > 0 && (
          <p className="palette-empty">No favourites yet.</p>
        )}

        {!loading && jobs.length === 0 && (
          <div className="empty">
            <Icon name="wave" size={20} />
            <p>Nothing rendered yet. Your takes will collect here.</p>
          </div>
        )}

        {loading && jobs.length === 0 && (
          <div className="empty">
            <span className="spinner" />
            <p>Loading sessions…</p>
          </div>
        )}
      </div>
    </section>
  );
}
