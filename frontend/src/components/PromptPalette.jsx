import { useMemo, useState } from 'react';
import Icon from './Icon';
import {
  ELEMENT_GROUPS,
  STARTERS,
  STARTER_FAMILIES,
  TARGET_WORDS,
  hasElement,
  segments,
  toggleElement,
  wordCount,
} from '../lib/promptLibrary';

function matches(haystack, needle) {
  return haystack.toLowerCase().includes(needle);
}

/** Starter cards, grouped by family and filtered by the shared search. */
function Starters({ query, onApply }) {
  const families = useMemo(() => {
    const term = query.trim().toLowerCase();
    return STARTER_FAMILIES.map((family) => ({
      ...family,
      items: STARTERS.filter(
        (starter) =>
          starter.family === family.id &&
          (!term || matches(starter.name, term) || matches(starter.prompt, term) || matches(family.label, term)),
      ),
    })).filter((family) => family.items.length > 0);
  }, [query]);

  if (families.length === 0) {
    return <p className="palette-empty">No starters match “{query}”.</p>;
  }

  return (
    <>
      {families.map((family) => (
        <section key={family.id} className="palette-group">
          <h3 className="palette-group-label">{family.label}</h3>
          {family.items.map((starter) => (
            <button key={starter.id} type="button" className="starter" onClick={() => onApply(starter)}>
              <span className="starter-head">
                <span className="starter-name">{starter.name}</span>
                <span className="starter-meta mono">
                  {starter.bpm} · {starter.instrumental ? 'inst' : 'vocal'}
                </span>
              </span>
              <span className="starter-prompt">{starter.prompt}</span>
            </button>
          ))}
        </section>
      ))}
    </>
  );
}

/**
 * Individual descriptors. Each chip toggles a comma-separated fragment in the
 * caption, so clicking twice removes it and anything typed by hand survives.
 */
function Elements({ query, prompt, onToggle }) {
  const groups = useMemo(() => {
    const term = query.trim().toLowerCase();
    return ELEMENT_GROUPS.map((group) => ({
      ...group,
      matched: term ? group.items.filter((item) => matches(item, term)) : group.items,
    })).filter((group) => group.matched.length > 0);
  }, [query]);

  if (groups.length === 0) {
    return <p className="palette-empty">No elements match “{query}”.</p>;
  }

  return (
    <>
      {groups.map((group) => {
        const active = group.matched.filter((item) => hasElement(prompt, item)).length;
        return (
          <section key={group.id} className="palette-group">
            <h3 className="palette-group-label">
              {group.label}
              {active > 0 && <span className="palette-count">{active}</span>}
            </h3>
            <p className="palette-hint">{group.hint}</p>
            <div className="element-grid">
              {group.matched.map((item) => {
                const on = hasElement(prompt, item);
                return (
                  <button
                    key={item}
                    type="button"
                    className={`element ${on ? 'is-on' : ''}`}
                    aria-pressed={on}
                    onClick={() => onToggle(item)}
                  >
                    {item}
                  </button>
                );
              })}
            </div>
          </section>
        );
      })}
    </>
  );
}

export default function PromptPalette({ prompt, onApplyStarter, onSetPrompt, onUndo, canUndo }) {
  const [tab, setTab] = useState('starters');
  const [query, setQuery] = useState('');

  const words = wordCount(prompt);
  // The model's shipped captions cluster near TARGET_WORDS; this is a nudge,
  // not a rule, so it stays a quiet line rather than a warning.
  const lengthNote =
    words === 0
      ? 'Aim for about two sentences.'
      : words < 12
        ? 'A little more detail usually helps.'
        : words > TARGET_WORDS * 2.4
          ? 'Long captions start to lose focus.'
          : 'Good length.';

  // Naming several genres at once is a documented way to muddy the output.
  const genreGroup = ELEMENT_GROUPS.find((group) => group.id === 'genre');
  const genreCount = genreGroup ? genreGroup.items.filter((item) => hasElement(prompt, item)).length : 0;

  return (
    <aside className="palette" aria-label="Prompt library">
      <div className="palette-top">
        <div className="palette-tabs" role="tablist" aria-label="Prompt library sections">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'starters'}
            className={tab === 'starters' ? 'is-on' : ''}
            onClick={() => setTab('starters')}
          >
            Starters
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'elements'}
            className={tab === 'elements' ? 'is-on' : ''}
            onClick={() => setTab('elements')}
          >
            Elements
          </button>
        </div>

        <div className="palette-search">
          <Icon name="search" size={14} />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={tab === 'starters' ? 'Search starters' : 'Search elements'}
            aria-label="Search the prompt library"
          />
          {query && (
            <button type="button" className="ghost-button" onClick={() => setQuery('')} aria-label="Clear search">
              <Icon name="close" size={13} />
            </button>
          )}
        </div>
      </div>

      <div className="palette-scroll">
        {tab === 'starters' ? (
          <Starters query={query} onApply={onApplyStarter} />
        ) : (
          <Elements query={query} prompt={prompt} onToggle={(item) => onSetPrompt(toggleElement(prompt, item))} />
        )}
      </div>

      <footer className="palette-foot">
        <span className="palette-note">
          {segments(prompt).length > 0 && <span className="mono">{words}w</span>} {lengthNote}
          {genreCount > 2 && ' Several genres at once tend to blur.'}
        </span>
        {canUndo && (
          <button type="button" className="palette-undo" onClick={onUndo}>
            <Icon name="undo" size={13} /> Undo
          </button>
        )}
      </footer>
    </aside>
  );
}
