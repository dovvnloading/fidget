import { useCallback, useEffect, useLayoutEffect, useRef } from 'react';

/** Canvas peak display for real decoded audio. `peaks` of null renders a rest state. */
export default function Waveform({ peaks, progress = 0, onSeek, height = 56 }) {
  const canvasRef = useRef(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const box = canvas.getBoundingClientRect();
    if (box.width === 0) return;

    const dpr = window.devicePixelRatio || 1;
    const width = Math.round(box.width * dpr);
    const tall = Math.round(box.height * dpr);
    if (canvas.width !== width || canvas.height !== tall) {
      canvas.width = width;
      canvas.height = tall;
    }

    const ctx = canvas.getContext('2d');
    const styles = getComputedStyle(canvas);
    const played = styles.getPropertyValue('--wave-played').trim() || '#f07b5e';
    const ahead = styles.getPropertyValue('--wave-ahead').trim() || '#4a4842';

    ctx.clearRect(0, 0, width, tall);

    const barWidth = 2 * dpr;
    const gap = 2 * dpr;
    const step = barWidth + gap;
    const count = Math.max(1, Math.floor(width / step));
    const middle = tall / 2;
    const cutoff = progress * count;

    for (let index = 0; index < count; index += 1) {
      let magnitude = 0.06;
      if (peaks && peaks.length) {
        const position = (index / count) * peaks.length;
        const low = Math.floor(position);
        const high = Math.min(peaks.length - 1, low + 1);
        const blend = position - low;
        magnitude = peaks[low] * (1 - blend) + peaks[high] * blend;
        magnitude = Math.max(0.035, magnitude);
      }
      const barHeight = Math.max(barWidth, magnitude * (tall - 2 * dpr));
      ctx.fillStyle = index < cutoff ? played : ahead;
      const x = index * step;
      const y = middle - barHeight / 2;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barHeight, barWidth / 2);
      ctx.fill();
    }
  }, [peaks, progress]);

  // Drawn synchronously after layout: a backgrounded or minimised window
  // never fires requestAnimationFrame, which would leave the canvas blank.
  useLayoutEffect(draw, [draw]);

  useEffect(() => {
    const observer = new ResizeObserver(draw);
    if (canvasRef.current) observer.observe(canvasRef.current);
    return () => observer.disconnect();
  }, [draw]);

  const seekTo = (event) => {
    if (!onSeek) return;
    const box = event.currentTarget.getBoundingClientRect();
    onSeek(Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)));
  };

  return (
    <div
      className={`waveform ${onSeek ? 'seekable' : ''}`}
      style={{ height }}
      onPointerDown={(event) => {
        if (!onSeek) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        seekTo(event);
      }}
      onPointerMove={(event) => {
        if (event.buttons === 1) seekTo(event);
      }}
      role={onSeek ? 'slider' : undefined}
      aria-label={onSeek ? 'Seek within track' : undefined}
      aria-valuenow={onSeek ? Math.round(progress * 100) : undefined}
      aria-valuemin={onSeek ? 0 : undefined}
      aria-valuemax={onSeek ? 100 : undefined}
      tabIndex={onSeek ? 0 : undefined}
      onKeyDown={(event) => {
        if (!onSeek) return;
        if (event.key === 'ArrowRight') onSeek(Math.min(1, progress + 0.02));
        if (event.key === 'ArrowLeft') onSeek(Math.max(0, progress - 0.02));
      }}
    >
      <canvas ref={canvasRef} />
      {!peaks && <span className="waveform-rest" />}
    </div>
  );
}
