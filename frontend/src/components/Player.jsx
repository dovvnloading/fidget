import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import Waveform from './Waveform';
import { usePeaks } from '../lib/peaks';
import { clock, megabytes } from '../lib/jobs';
import { mediaUrl } from '../lib/api';

function Metric({ label, value, mono }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className={`metric-value ${mono ? 'mono' : ''}`}>{value}</span>
    </div>
  );
}

export default function Player({ job, onReuse, onHeard }) {
  const audioRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [volume, setVolume] = useState(() => {
    const stored = Number(window.localStorage?.getItem('fidget:volume'));
    return Number.isFinite(stored) && stored > 0 && stored <= 1 ? stored : 1;
  });
  const [muted, setMuted] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const src = mediaUrl(job?.result_url);
  const peaks = usePeaks(src);
  const metrics = job?.metrics ?? {};
  const duration = Number(metrics.audio_duration_seconds) || peaks?.duration || Number(job?.duration) || 0;
  const progress = duration > 0 ? Math.min(1, time / duration) : 0;

  // A new track loads paused at zero; the user chooses when it plays.
  useEffect(() => {
    setTime(0);
    setPlaying(false);
    setExpanded(false);
  }, [job?.id]);

  // Level lives on the element, so it applies to the already-loaded track and
  // survives swapping to a different one.
  useEffect(() => {
    const audio = audioRef.current;
    if (audio) audio.volume = volume;
    window.localStorage?.setItem('fidget:volume', String(volume));
  }, [volume, job?.id]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return undefined;
    const onTime = () => setTime(audio.currentTime);
    const onEnd = () => {
      setPlaying(false);
      setTime(0);
    };
    // A take counts as heard once it actually plays, not merely when selected.
    const onPlay = () => onHeard?.(job?.id);
    audio.addEventListener('timeupdate', onTime);
    audio.addEventListener('ended', onEnd);
    audio.addEventListener('play', onPlay);
    return () => {
      audio.removeEventListener('timeupdate', onTime);
      audio.removeEventListener('ended', onEnd);
      audio.removeEventListener('play', onPlay);
    };
  }, [job?.id, onHeard]);

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    } else {
      audio.pause();
      setPlaying(false);
    }
  };

  const seek = (ratio) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    audio.currentTime = ratio * duration;
    setTime(audio.currentTime);
  };

  const nudge = (delta) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = Math.min(duration, Math.max(0, audio.currentTime + delta));
    setTime(audio.currentTime);
  };

  // Space toggles playback unless the user is typing.
  useEffect(() => {
    const onKey = (event) => {
      if (event.code !== 'Space') return;
      const tag = event.target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || event.target?.isContentEditable) return;
      event.preventDefault();
      toggle();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [job?.id]);

  if (!job) return null;

  return (
    <section className={`player ${expanded ? 'is-expanded' : ''}`} aria-label="Now playing">
      <audio ref={audioRef} src={src} preload="metadata" muted={muted} />

      <div className="player-main">
        <button className="transport-play" type="button" onClick={toggle} aria-label={playing ? 'Pause' : 'Play'}>
          <Icon name={playing ? 'pause' : 'play'} size={19} />
        </button>

        <div className="transport-steps">
          <button type="button" onClick={() => nudge(-5)} aria-label="Back 5 seconds"><Icon name="skipBack" size={15} /></button>
          <button type="button" onClick={() => nudge(5)} aria-label="Forward 5 seconds"><Icon name="skipForward" size={15} /></button>
        </div>

        <div className="player-track">
          <Waveform peaks={peaks?.values} progress={progress} onSeek={seek} height={48} />
        </div>

        <div className="player-time mono">
          <span>{clock(time)}</span>
          <span className="player-time-total">{clock(duration)}</span>
        </div>

        <div className="player-actions">
          <div className="volume">
            <button
              type="button"
              className="ghost-button"
              onClick={() => setMuted((value) => !value)}
              aria-label={muted ? 'Unmute' : 'Mute'}
            >
              <Icon name={muted || volume === 0 ? 'mute' : 'volume'} size={16} />
            </button>
            <input
              className="volume-slider"
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={muted ? 0 : volume}
              onChange={(event) => {
                setVolume(Number(event.target.value));
                setMuted(false);
              }}
              aria-label="Volume"
              style={{ '--fill': `${(muted ? 0 : volume) * 100}%` }}
            />
          </div>
          <button type="button" className="ghost-button" onClick={() => onReuse(job)} title="Load these settings into the composer">
            <Icon name="copy" size={16} />
          </button>
          <a className="ghost-button" href={src} download title="Download WAV">
            <Icon name="download" size={16} />
          </a>
          <button
            type="button"
            className={`ghost-button ${expanded ? 'is-on' : ''}`}
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            title="Render details"
          >
            <Icon name="info" size={16} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="player-details">
          <div className="metric-row">
            <Metric label="Render time" value={metrics.elapsed_seconds ? `${Number(metrics.elapsed_seconds).toFixed(1)}s` : null} mono />
            <Metric label="Peak VRAM" value={megabytes(metrics.peak_gpu_used_mb)} mono />
            <Metric label="Peak worker RSS" value={megabytes(metrics.peak_worker_rss_mb)} mono />
            <Metric label="Measured length" value={metrics.audio_duration_seconds ? `${Number(metrics.audio_duration_seconds).toFixed(2)}s` : null} mono />
            <Metric label="Loudness (RMS)" value={metrics.audio_rms ? Number(metrics.audio_rms).toFixed(3) : null} mono />
            <Metric label="Seed" value={job.seed ?? 'random'} mono />
            <Metric label="Key" value={job.key_scale || 'any'} />
            <Metric label="Tempo" value={job.bpm ? `${job.bpm} BPM` : 'free'} />
          </div>
          {metrics.sha256 && (
            <p className="checksum mono">
              <Icon name="shield" size={13} /> SHA-256 {String(metrics.sha256).slice(0, 32)}…
            </p>
          )}
          <p className="player-prompt">{job.prompt}</p>
        </div>
      )}
    </section>
  );
}
