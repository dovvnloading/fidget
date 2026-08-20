/*
 * Every glyph is drawn so its *ink* is centred on (12, 12) of the 24x24 box and
 * spans a consistent optical size, so icons sitting side by side in a button row
 * read as the same weight. Two families:
 *
 *   stroked — geometry spans roughly 4..20; the 1.7 stroke takes ink to ~17.7
 *   solid   — geometry is stroked in the same colour with a round join, which
 *             softens the corners and lets ink be tuned to ~16 (solid shapes
 *             read heavier than outlines, so they are drawn slightly smaller)
 *
 * The one deliberate exception is `play`: a right-pointing triangle looks
 * off-centre when its bounding box is centred, so its ink is nudged +0.6 right.
 * That nudge lives here, in the geometry — never as padding on a button, which
 * would also displace the `pause` glyph that replaces it.
 */

const SOLID = new Set(['play', 'pause', 'skipBack', 'skipForward']);

const PATHS = {
  // Solid transport glyphs
  play: <path d="M8.1 5.1v13.8a.9.9 0 0 0 1.38.76l10.4-6.9a.9.9 0 0 0 0-1.52L9.48 4.34A.9.9 0 0 0 8.1 5.1Z" />,
  pause: <><rect x="7.4" y="4.2" width="3.5" height="15.6" rx="1.1" /><rect x="13.1" y="4.2" width="3.5" height="15.6" rx="1.1" /></>,
  skipBack: <><path d="M19 5.9v12.2a.7.7 0 0 1-1.08.6l-9.2-6.1a.7.7 0 0 1 0-1.2l9.2-6.1a.7.7 0 0 1 1.08.6Z" /><rect x="5" y="5.4" width="2.4" height="13.2" rx="1.2" /></>,
  skipForward: <><path d="M5 5.9v12.2a.7.7 0 0 0 1.08.6l9.2-6.1a.7.7 0 0 0 0-1.2l-9.2-6.1A.7.7 0 0 0 5 5.9Z" /><rect x="16.6" y="5.4" width="2.4" height="13.2" rx="1.2" /></>,

  // Stroked glyphs
  download: <><path d="M12 4.4v10.4" /><path d="m7.6 10.6 4.4 4.4 4.4-4.4" /><path d="M4.6 19.6h14.8" /></>,
  refresh: <><path d="M20 11.1a8 8 0 0 0-14.2-4.4L4.3 8.6" /><path d="M4 4.4v4.6h4.6" /><path d="M4 12.9a8 8 0 0 0 14.2 4.4l1.5-1.9" /><path d="M20 19.6V15h-4.6" /></>,
  close: <><path d="M4.9 4.9l14.2 14.2" /><path d="M19.1 4.9 4.9 19.1" /></>,
  alert: <><path d="M12 4.3 3.6 19.7h16.8L12 4.3Z" /><path d="M12 10.2v4.1" /><path d="M12 17.2h.01" /></>,
  shield: <><path d="M12 4 5.2 6.6v5.1c0 4.1 2.8 7.4 6.8 8.9 4-1.5 6.8-4.8 6.8-8.9V6.6L12 4Z" /><path d="m9.1 11.9 2.1 2.1 3.9-4" /></>,
  chip: <><rect x="7.3" y="7.3" width="9.4" height="9.4" rx="2" /><path d="M10 4v3.3M14 4v3.3M10 16.7V20M14 16.7V20M4 10h3.3M4 14h3.3M16.7 10H20M16.7 14H20" /></>,
  info: <><circle cx="12" cy="12" r="8" /><path d="M12 11.1v5" /><path d="M12 7.9h.01" /></>,
  volume: <><path d="M4.6 9.4h3L11.4 5.9v12.2L7.6 14.6h-3V9.4Z" /><path d="M15.1 9.6a3.5 3.5 0 0 1 0 4.8" /><path d="M17.9 6.9a7.3 7.3 0 0 1 0 10.2" /></>,
  mute: <><path d="M4.6 9.4h3L11.4 5.9v12.2L7.6 14.6h-3V9.4Z" /><path d="m15.2 9.9 4.2 4.2" /><path d="m19.4 9.9-4.2 4.2" /></>,
  power: <><path d="M12 4v8.2" /><path d="M7.3 6.9a7.6 7.6 0 1 0 9.4 0" /></>,
  dice: <><rect x="4" y="4" width="16" height="16" rx="3.8" /><path d="M8.9 8.9h.01M15.1 15.1h.01M12 12h.01" /></>,
  copy: <><rect x="8.6" y="8.6" width="11.4" height="11.4" rx="2.4" /><path d="M15.6 5.1H6.4A2.4 2.4 0 0 0 4 7.5v9.2" /></>,
  wave: <path d="M4 12h1.6l1.5-6.4L9.6 18.6 12 4.6l2.3 14L16.4 8l1.5 6.6 1-2.6H20" />,
  search: <><circle cx="10.6" cy="10.6" r="6.4" /><path d="m15.4 15.4 4.4 4.4" /></>,
  arrowUp: <><path d="M12 19.2V4.8" /><path d="m6.6 10.4 5.4-5.6 5.4 5.6" /></>,
  trash: <><path d="M4.4 6.6h15.2" /><path d="M9.6 6.6V4.9h4.8v1.7" /><path d="M6.3 6.6 7.2 19.4h9.6l.9-12.8" /><path d="M10.3 10v6M13.7 10v6" /></>,
  thumbUp: <><rect x="3.9" y="10.4" width="4.1" height="9.2" rx="1.3" /><path d="M8 11.2 11.6 4.3h.9a2 2 0 0 1 2 2v3.9h4.1a1.9 1.9 0 0 1 1.85 2.35l-1.3 5.9a1.9 1.9 0 0 1-1.85 1.5H8" /></>,
  thumbDown: <><rect x="3.9" y="4.4" width="4.1" height="9.2" rx="1.3" /><path d="M8 12.8 11.6 19.7h.9a2 2 0 0 0 2-2v-3.9h4.1a1.9 1.9 0 0 0 1.85-2.35l-1.3-5.9A1.9 1.9 0 0 0 16.7 4.1H8" /></>,
  star: <path d="m12 4.2 2.42 4.9 5.41.79-3.92 3.81.93 5.39L12 16.55l-4.84 2.54.93-5.39-3.92-3.81 5.41-.79L12 4.2Z" />,
  grid: <><rect x="4.2" y="4.2" width="6.4" height="6.4" rx="1.6" /><rect x="13.4" y="4.2" width="6.4" height="6.4" rx="1.6" /><rect x="4.2" y="13.4" width="6.4" height="6.4" rx="1.6" /><rect x="13.4" y="13.4" width="6.4" height="6.4" rx="1.6" /></>,
  undo: <><path d="M4.4 9.4h6.2" /><path d="M4.4 9.4V4" /><path d="M4.4 9.4 8 6.2a7.6 7.6 0 1 1-1.6 8.3" /></>,
};

/*
 * Residual centring corrections, in user units, measured from the rendered
 * geometry rather than computed by hand — curve and arc extents do not fall
 * where the control points suggest. To re-measure after editing a path, render
 * the glyph and compare `getBBox()` (grown by half the stroke width) against
 * the centre of the 24x24 box; the correction is the difference.
 *
 * `play` additionally carries a deliberate +0.6 optical nudge: a right-pointing
 * triangle reads as left-of-centre when its bounding box is centred.
 */
const NUDGE = {
  play: [-1.6, 0],
  shield: [0, -0.3],
  volume: [-0.3, 0],
  power: [0, -0.25],
  copy: [0, -0.55],
  wave: [0, 0.4],
  trash: [0, -0.15],
  thumbUp: [-0.2, -0.13],
  thumbDown: [-0.2, 0.15],
  star: [0, 0.36],
  undo: [-0.7, 0.45],
};

export default function Icon({ name, size = 18, strokeWidth = 1.7 }) {
  const path = PATHS[name];
  if (!path) return null;

  const solid = SOLID.has(name);
  const [dx, dy] = NUDGE[name] ?? [0, 0];

  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={solid ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth={solid ? 1.3 : strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {dx || dy ? <g transform={`translate(${dx} ${dy})`}>{path}</g> : path}
    </svg>
  );
}
