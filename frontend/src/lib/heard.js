import { useCallback, useEffect, useRef, useState } from 'react';
import { isPlayable } from './jobs';

const KEY = 'fidget:heard';

function load() {
  try {
    const raw = window.localStorage?.getItem(KEY);
    // null means "never initialised", which is different from "nothing heard".
    return raw ? new Set(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
}

function persist(ids) {
  try {
    window.localStorage?.setItem(KEY, JSON.stringify([...ids]));
  } catch {
    /* Highlighting is cosmetic; never let storage limits break playback. */
  }
}

/**
 * Tracks which finished takes the user has actually listened to, so new ones
 * can be marked in the library without any accompanying label.
 *
 * `ready` must be true only once the first jobs response has arrived. On the
 * very first run everything already in the library is treated as heard --
 * otherwise opening the app would light up the user's entire back catalogue --
 * but a fresh install with no history correctly marks its first take as new.
 */
export function useHeard(jobs, ready) {
  const [heard, setHeard] = useState(load);
  const seeded = useRef(heard !== null);

  useEffect(() => {
    if (seeded.current || !ready) return;
    seeded.current = true;
    const existing = new Set(jobs.filter(isPlayable).map((job) => job.id));
    persist(existing);
    setHeard(existing);
  }, [jobs, ready]);

  const markHeard = useCallback((id) => {
    if (!id) return;
    setHeard((current) => {
      const base = current ?? new Set();
      if (base.has(id)) return current;
      const next = new Set(base);
      next.add(id);
      persist(next);
      return next;
    });
  }, []);

  const isUnheard = useCallback(
    (job) => heard !== null && isPlayable(job) && !heard.has(job.id),
    [heard],
  );

  return { isUnheard, markHeard };
}
