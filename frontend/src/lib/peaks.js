import { useEffect, useState } from 'react';

const BUCKETS = 320;
const cache = new Map();
let context = null;

function audioContext() {
  if (!context) {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    context = Ctor ? new Ctor() : null;
  }
  return context;
}

/** Peak envelope of the real rendered audio, normalised to 0..1. */
async function extract(url) {
  const ctx = audioContext();
  if (!ctx) throw new Error('Web Audio unavailable');
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not read audio (${response.status})`);
  const buffer = await ctx.decodeAudioData(await response.arrayBuffer());

  const channels = Array.from({ length: buffer.numberOfChannels }, (_, index) =>
    buffer.getChannelData(index),
  );
  const span = Math.max(1, Math.floor(buffer.length / BUCKETS));
  const values = new Float32Array(BUCKETS);
  let ceiling = 0;

  for (let bucket = 0; bucket < BUCKETS; bucket += 1) {
    const start = bucket * span;
    const end = Math.min(buffer.length, start + span);
    let peak = 0;
    for (let index = start; index < end; index += 1) {
      for (const channel of channels) {
        const magnitude = Math.abs(channel[index]);
        if (magnitude > peak) peak = magnitude;
      }
    }
    values[bucket] = peak;
    if (peak > ceiling) ceiling = peak;
  }

  if (ceiling > 0) {
    for (let index = 0; index < BUCKETS; index += 1) values[index] /= ceiling;
  }
  return { values, duration: buffer.duration };
}

/**
 * Real peaks for a rendered track. Falls back to null while loading or on
 * failure so the player can show a neutral placeholder instead of fake data.
 */
export function usePeaks(url) {
  const [state, setState] = useState(() => cache.get(url) ?? null);

  useEffect(() => {
    if (!url) {
      setState(null);
      return undefined;
    }
    const cached = cache.get(url);
    if (cached) {
      setState(cached);
      return undefined;
    }
    let live = true;
    setState(null);
    extract(url)
      .then((result) => {
        cache.set(url, result);
        if (live) setState(result);
      })
      .catch(() => {
        if (live) setState({ values: null, duration: 0 });
      });
    return () => {
      live = false;
    };
  }, [url]);

  return state;
}
