/*
 * Prompt material for ACE-Step 1.5.
 *
 * Shape follows the model's own guidance (docs/en/ace_step_musicians_guide.md,
 * "Writing Prompts"), which asks a caption to name four things: genre,
 * instruments, mood, and production style. The starters below match the
 * structure of the 200 captions shipped in the model's examples/ directory --
 * two sentences, a median of ~32 words:
 *
 *   "A <mood> <genre> track with <instruments> and <vocal>.
 *    Features <detail>, <detail>, and <production/atmosphere>."
 *
 * Starters also carry bpm/key/duration because the shipped examples always do,
 * and those values are what make a caption land as written.
 */

export const STARTER_FAMILIES = [
  { id: 'electronic', label: 'Electronic' },
  { id: 'hiphop', label: 'Hip-Hop & R&B' },
  { id: 'rock', label: 'Rock & Metal' },
  { id: 'jazz', label: 'Jazz & Soul' },
  { id: 'folk', label: 'Folk & Acoustic' },
  { id: 'cinematic', label: 'Cinematic' },
  { id: 'ambient', label: 'Ambient & Experimental' },
  { id: 'pop', label: 'Pop' },
];

export const STARTERS = [
  // ---- Electronic ---------------------------------------------------------
  {
    id: 'midnight-drive',
    name: 'Midnight Drive',
    family: 'electronic',
    prompt:
      'A nocturnal synthwave track with arpeggiated analog synths, gated reverb drums, and a fretless bass line. Features neon-lit pads, a slow-building melodic lead, and glossy 1980s production.',
    bpm: 108,
    key: 'A Minor',
    duration: 120,
    instrumental: true,
  },
  {
    id: 'sunrise-house',
    name: 'Sunrise House',
    family: 'electronic',
    prompt:
      'A euphoric deep house track with warm sub-bass, filtered piano chords, and airy female vocal hooks. Features a four-on-the-floor kick, shuffled hi-hats, and bright, open-air production.',
    bpm: 122,
    key: 'F Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'concrete-room',
    name: 'Concrete Room',
    family: 'electronic',
    prompt:
      'A relentless industrial techno track with a distorted kick, metallic percussion loops, and corroded synth stabs. Features rumbling sub-bass, tape-saturated noise sweeps, and a cold warehouse atmosphere.',
    bpm: 138,
    key: 'D Minor',
    duration: 150,
    instrumental: true,
  },
  {
    id: 'paper-lanterns',
    name: 'Paper Lanterns',
    family: 'electronic',
    prompt:
      'A weightless ambient techno track with granular pads, a soft dub-chord bassline, and brushed electronic percussion. Features slow filter movement, long tape delays, and a spacious, patient mix.',
    bpm: 118,
    key: 'E Minor',
    duration: 180,
    instrumental: true,
  },

  // ---- Hip-Hop & R&B ------------------------------------------------------
  {
    id: 'dusty-tape',
    name: 'Dusty Tape',
    family: 'hiphop',
    prompt:
      'A nostalgic boom-bap hip-hop track with a chopped soul sample, upright bass, and a crisp swung snare. Features vinyl crackle, muted rhodes chords, and warm, lo-fi production.',
    bpm: 88,
    key: 'F Minor',
    duration: 120,
    instrumental: true,
  },
  {
    id: 'late-shift',
    name: 'Late Shift',
    family: 'hiphop',
    prompt:
      'A smooth contemporary R&B track with chorused electric guitar, round synth bass, and an emotive male tenor vocal. Features layered harmonies, an unobtrusive drum machine groove, and polished late-night production.',
    bpm: 94,
    key: 'A Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'low-ceiling',
    name: 'Low Ceiling',
    family: 'hiphop',
    prompt:
      'A menacing trap track with sliding 808 bass, rapid hi-hat rolls, and a sparse, brooding piano motif. Features cavernous reverb, half-time drums, and dark, heavily compressed production.',
    bpm: 140,
    key: 'C Minor',
    duration: 120,
    instrumental: true,
  },
  {
    id: 'kitchen-floor',
    name: 'Kitchen Floor',
    family: 'hiphop',
    prompt:
      'An intimate neo-soul track with gospel organ, brushed drums, and a breathy female vocal. Features extended jazz chords, a walking bassline, and close-mic, unhurried production.',
    bpm: 74,
    key: 'D Major',
    duration: 150,
    instrumental: false,
  },

  // ---- Rock & Metal -------------------------------------------------------
  {
    id: 'gravel-road',
    name: 'Gravel Road',
    family: 'rock',
    prompt:
      'A driving garage rock track with crunchy rhythm guitar, a punchy snare, and gravelly male vocals. Features an overdriven bass, a raw live-room drum sound, and unpolished analog production.',
    bpm: 132,
    key: 'E Minor',
    duration: 120,
    instrumental: false,
  },
  {
    id: 'cold-angles',
    name: 'Cold Angles',
    family: 'rock',
    prompt:
      'A melancholic post-punk track with angular guitar riffs, a driving bassline, and brooding baritone vocals. Features cold synth textures, mechanical drums, and a dark, reverberant production style.',
    bpm: 125,
    key: 'C Minor',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'stadium-light',
    name: 'Stadium Light',
    family: 'rock',
    prompt:
      'An anthemic arena rock track with layered electric guitars, a soaring lead vocal, and a huge backbeat. Features stacked gang vocals, a triumphant final lift, and glossy stadium production.',
    bpm: 128,
    key: 'D Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'iron-weather',
    name: 'Iron Weather',
    family: 'rock',
    prompt:
      'A heavy sludge metal track with downtuned distorted guitars, thunderous double-kick drums, and roared vocals. Features slow crushing riffs, feedback swells, and thick, oppressive production.',
    bpm: 96,
    key: 'B Minor',
    duration: 150,
    instrumental: false,
  },

  // ---- Jazz & Soul --------------------------------------------------------
  {
    id: 'blue-hour',
    name: 'Blue Hour',
    family: 'jazz',
    prompt:
      'A wistful jazz trio piece with brushed drums, upright bass, and expressive acoustic piano. Features extended voicings, a relaxed swung feel, and warm, roomy live production.',
    bpm: 92,
    key: 'E Minor',
    duration: 150,
    instrumental: true,
  },
  {
    id: 'brass-district',
    name: 'Brass District',
    family: 'jazz',
    prompt:
      'An exuberant funk track with a tight horn section, slap bass, and a syncopated clavinet riff. Features punchy drums, call-and-response vocal shouts, and bright, vintage production.',
    bpm: 112,
    key: 'G Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'velvet-lounge',
    name: 'Velvet Lounge',
    family: 'jazz',
    prompt:
      'A sultry lounge jazz track with muted trumpet, vibraphone, and a smoky female vocal. Features a walking bassline, soft brushed snare, and intimate, tape-warm production.',
    bpm: 84,
    key: 'F Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'sunday-organ',
    name: 'Sunday Organ',
    family: 'jazz',
    prompt:
      'A joyful gospel soul track with hammond organ, a full choir, and a powerful lead female vocal. Features hand claps, a driving piano, and rich, live-congregation production.',
    bpm: 100,
    key: 'C Major',
    duration: 150,
    instrumental: false,
  },

  // ---- Folk & Acoustic ----------------------------------------------------
  {
    id: 'kitchen-table',
    name: 'Kitchen Table',
    family: 'folk',
    prompt:
      'A tender indie folk track with fingerpicked acoustic guitar, soft upright bass, and breathy female vocals. Features close vocal harmonies, brushed percussion, and intimate, near-silent room production.',
    bpm: 84,
    key: 'G Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'porch-light',
    name: 'Porch Light',
    family: 'folk',
    prompt:
      'A weathered americana track with slide guitar, banjo, and a warm male baritone vocal. Features a shuffling brush groove, fiddle counter-melodies, and dusty, live-room production.',
    bpm: 96,
    key: 'D Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'grey-window',
    name: 'Grey Window',
    family: 'folk',
    prompt:
      'A melancholic piano ballad with soft female vocals, gentle string accompaniment, and sparse arrangement. Features delicate dynamics, unhurried phrasing, and an intimate, heartbreaking atmosphere.',
    bpm: 68,
    key: 'A Minor',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'field-recording',
    name: 'Field Recording',
    family: 'folk',
    prompt:
      'A pastoral acoustic instrumental with nylon-string guitar, hammered dulcimer, and light hand percussion. Features open tunings, a gentle lilting rhythm, and natural, unprocessed production.',
    bpm: 88,
    key: 'C Major',
    duration: 120,
    instrumental: true,
  },

  // ---- Cinematic ----------------------------------------------------------
  {
    id: 'rising-tide',
    name: 'Rising Tide',
    family: 'cinematic',
    prompt:
      'A sweeping orchestral cue with soaring strings, French horns, and thunderous timpani. Features a slow heroic build, choral swells, and wide, epic film-score production.',
    bpm: 90,
    key: 'D Major',
    duration: 150,
    instrumental: true,
  },
  {
    id: 'cold-open',
    name: 'Cold Open',
    family: 'cinematic',
    prompt:
      'A tense hybrid score with pulsing low strings, metallic percussion, and an ominous synth drone. Features rhythmic ostinatos, sudden dynamic drops, and dark, modern trailer production.',
    bpm: 110,
    key: 'D Minor',
    duration: 120,
    instrumental: true,
  },
  {
    id: 'small-hours',
    name: 'Small Hours',
    family: 'cinematic',
    prompt:
      'A fragile solo piano piece with distant string pads and faint room noise. Features sparse melodic phrasing, generous sustain, and close, felt-piano production.',
    bpm: 62,
    key: 'F Major',
    duration: 120,
    instrumental: true,
  },
  {
    id: 'long-shadow',
    name: 'Long Shadow',
    family: 'cinematic',
    prompt:
      'A brooding neo-noir cue with muted trumpet, upright bass, and shimmering vibraphone. Features smoky harmonic movement, brushed drums, and moody, rain-soaked production.',
    bpm: 76,
    key: 'B Minor',
    duration: 150,
    instrumental: true,
  },

  // ---- Ambient & Experimental ---------------------------------------------
  {
    id: 'slow-tape',
    name: 'Slow Tape',
    family: 'ambient',
    prompt:
      'A drifting ambient piece with warm tape-saturated pads, distant piano, and gentle analog hiss. Features long evolving swells, no percussion, and hazy, lo-fi cassette production.',
    bpm: 70,
    key: 'C Major',
    duration: 180,
    instrumental: true,
  },
  {
    id: 'glass-structures',
    name: 'Glass Structures',
    family: 'ambient',
    prompt:
      'A minimalist generative piece with interlocking marimba patterns, glassy synth tones, and soft sine bass. Features slow phasing repetition, subtle detuning, and clean, spacious production.',
    bpm: 100,
    key: 'E Minor',
    duration: 180,
    instrumental: true,
  },
  {
    id: 'signal-decay',
    name: 'Signal Decay',
    family: 'ambient',
    prompt:
      'A corroded experimental piece with granular textures, bit-crushed melodic fragments, and irregular clicks. Features unstable pitch drift, wide stereo noise, and raw, unresolved production.',
    bpm: 80,
    key: 'A Minor',
    duration: 150,
    instrumental: true,
  },
  {
    id: 'deep-current',
    name: 'Deep Current',
    family: 'ambient',
    prompt:
      'A submerged dub techno piece with heavily filtered chord stabs, deep sub-bass, and cavernous delay. Features a muffled steady pulse, slow tidal movement, and murky underwater production.',
    bpm: 120,
    key: 'F Minor',
    duration: 180,
    instrumental: true,
  },

  // ---- Pop ----------------------------------------------------------------
  {
    id: 'summer-hooks',
    name: 'Summer Hooks',
    family: 'pop',
    prompt:
      'A bouncy electro-pop track with arpeggiated synths, a four-on-the-floor kick, and bright female vocals. Features catchy hooks, sidechained bass, and a playful, radio-ready mix.',
    bpm: 122,
    key: 'D Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'bedroom-window',
    name: 'Bedroom Window',
    family: 'pop',
    prompt:
      'A hazy bedroom pop track with jangly reverbed guitar, mellow synth pads, and soft doubled vocals. Features a relaxed backbeat, warm tape wobble, and intimate lo-fi production.',
    bpm: 98,
    key: 'G Major',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'night-bus',
    name: 'Night Bus',
    family: 'pop',
    prompt:
      'A moody synth-pop track with cold analog pads, a pulsing bassline, and detached female vocals. Features gated drums, melancholy hooks, and glossy, melancholic production.',
    bpm: 116,
    key: 'A Minor',
    duration: 150,
    instrumental: false,
  },
  {
    id: 'paper-planes',
    name: 'Paper Planes',
    family: 'pop',
    prompt:
      'An uplifting indie pop track with chiming guitars, group vocal chants, and a driving tambourine. Features a euphoric chorus, handclaps, and bright, energetic festival production.',
    bpm: 126,
    key: 'C Major',
    duration: 150,
    instrumental: false,
  },
];

/*
 * Building blocks. Categories mirror the four the model's guide asks you to
 * name, plus vocals and rhythm, which the shipped captions specify constantly.
 * Order matters: appended fragments read best genre-first, production-last.
 */
export const ELEMENT_GROUPS = [
  {
    id: 'genre',
    label: 'Genre',
    hint: 'Start here — the single biggest lever',
    items: [
      'synthwave', 'deep house', 'techno', 'ambient techno', 'dub techno', 'drum and bass',
      'breakbeat', 'trip-hop', 'downtempo', 'IDM', 'boom-bap hip-hop', 'trap', 'lo-fi hip-hop',
      'contemporary R&B', 'neo-soul', 'funk', 'disco', 'gospel soul', 'motown soul',
      'jazz trio', 'bebop', 'lounge jazz', 'bossa nova', 'garage rock', 'post-punk',
      'shoegaze', 'arena rock', 'psychedelic rock', 'sludge metal', 'black metal',
      'indie folk', 'americana', 'bluegrass', 'celtic folk', 'singer-songwriter',
      'orchestral film score', 'cinematic trailer', 'noir jazz', 'chamber music',
      'ambient', 'drone', 'minimalist', 'neoclassical',
      'electro-pop', 'synth-pop', 'bedroom pop', 'indie pop', 'city pop', 'dream pop',
    ],
  },
  {
    id: 'instruments',
    label: 'Instruments',
    hint: 'Name two or three — vague beats a long list',
    items: [
      'acoustic guitar', 'fingerpicked guitar', 'nylon-string guitar', 'electric guitar',
      'crunchy rhythm guitar', 'distorted guitar', 'slide guitar', 'jangly guitar',
      'banjo', 'mandolin', 'fiddle', 'upright bass', 'slap bass', 'fretless bass',
      'sub-bass', '808 bass', 'synth bass', 'acoustic piano', 'felt piano', 'rhodes',
      'wurlitzer', 'hammond organ', 'gospel organ', 'clavinet', 'analog synth',
      'arpeggiated synth', 'synth pads', 'mellotron', 'string section', 'cello',
      'solo violin', 'french horns', 'brass section', 'muted trumpet', 'saxophone',
      'flute', 'woodwinds', 'harp', 'vibraphone', 'marimba', 'hammered dulcimer',
      'timpani', 'brushed drums', 'live drum kit', 'drum machine', 'hand percussion',
      'tambourine', 'handclaps', 'choir', 'field recordings',
    ],
  },
  {
    id: 'vocals',
    label: 'Vocals',
    hint: 'Skip entirely for instrumental takes',
    items: [
      'breathy female vocals', 'powerful female vocals', 'smoky female vocals',
      'bright female vocals', 'detached female vocals', 'soulful female vocals',
      'gravelly male vocals', 'soft male vocals', 'male tenor vocals',
      'baritone vocals', 'falsetto', 'whispered vocals', 'spoken word',
      'rapped verses', 'melodic rap', 'layered harmonies', 'close vocal harmonies',
      'gang vocals', 'group chants', 'call-and-response', 'choral swells',
      'ad-libs', 'vocal chops', 'wordless vocals',
    ],
  },
  {
    id: 'mood',
    label: 'Mood',
    hint: 'One or two — conflicting moods muddy the result',
    items: [
      'melancholic', 'wistful', 'nostalgic', 'bittersweet', 'heartbroken', 'tender',
      'intimate', 'hopeful', 'uplifting', 'euphoric', 'triumphant', 'anthemic',
      'playful', 'carefree', 'dreamy', 'hazy', 'hypnotic', 'meditative', 'weightless',
      'brooding', 'ominous', 'tense', 'menacing', 'aggressive', 'relentless',
      'chaotic', 'unsettling', 'cold', 'warm', 'sultry', 'confident', 'defiant',
    ],
  },
  {
    id: 'rhythm',
    label: 'Rhythm & Feel',
    hint: 'How it moves, beyond raw tempo',
    items: [
      'four-on-the-floor kick', 'swung groove', 'shuffled hi-hats', 'half-time drums',
      'double-time feel', 'driving backbeat', 'punchy snare', 'crisp snare',
      'rapid hi-hat rolls', 'syncopated groove', 'polyrhythmic percussion',
      'motorik pulse', 'laid-back pocket', 'rubato', 'no percussion',
      'sparse arrangement', 'dense arrangement', 'slow build', 'sudden drop',
      'breakdown section', 'key change',
    ],
  },
  {
    id: 'production',
    label: 'Production',
    hint: 'Finish with how it was recorded and mixed',
    items: [
      'lo-fi production', 'polished production', 'radio-ready mix', 'live-room recording',
      'close-mic recording', 'vintage analog production', 'tape saturation', 'vinyl crackle',
      'tape wobble', 'bit-crushed', 'heavily compressed', 'wide stereo field',
      'cavernous reverb', 'gated reverb', 'long tape delay', 'dry and upfront',
      'muffled and distant', 'sidechained', 'glossy 1980s production',
      'bedroom production', 'orchestral film-score production', 'natural and unprocessed',
      'warm and roomy', 'dark and murky', 'bright and open-air',
    ],
  },
];

/** Structure tags the model reads from lyrics, per the musician's guide. */
export const LYRIC_SECTIONS = [
  '[Intro]', '[Verse 1]', '[Pre-Chorus]', '[Chorus]', '[Verse 2]',
  '[Bridge]', '[Instrumental]', '[Outro]',
];

/** Split a caption into the comma-separated fragments elements toggle against. */
export function segments(prompt) {
  return String(prompt || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

export function hasElement(prompt, element) {
  const target = element.toLowerCase();
  return segments(prompt).some((part) => part.toLowerCase() === target);
}

/** Toggle a fragment while leaving anything the user typed untouched. */
export function toggleElement(prompt, element) {
  const parts = segments(prompt);
  const target = element.toLowerCase();
  const without = parts.filter((part) => part.toLowerCase() !== target);
  if (without.length !== parts.length) return without.join(', ');
  return [...parts, element].join(', ');
}

/** The shipped captions cluster tightly around 32 words; used as soft guidance. */
export const TARGET_WORDS = 32;

export function wordCount(prompt) {
  return String(prompt || '').trim().split(/\s+/).filter(Boolean).length;
}
