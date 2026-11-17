import type { InjectionKey, Ref } from 'vue'
import type { LocalNote } from '@/db/schema'

export const NOTE_COLORS = [
  'default',
  'coral',
  'peach',
  'sand',
  'mint',
  'sage',
  'fog',
  'storm',
  'dusk',
  'blossom',
  'clay',
  'chalk',
] as const satisfies readonly LocalNote['color'][]

export type NoteColor = (typeof NOTE_COLORS)[number]

export function noteBackground(color: NoteColor): string {
  return `var(--note-${color})`
}

/**
 * The background of a card or the editor in the note's colour. On a coloured note the muted colour
 * of secondary text and icons is mostly ink, since plain muted grey falls below the WCAG contrast
 * on several note colours (down to 2.6:1); 85 % keeps at least 4.5:1 on all of them.
 */
export function noteSurface(color: NoteColor): Record<string, string> {
  if (color === 'default') return { background: noteBackground(color) }
  return {
    background: noteBackground(color),
    '--muted': `color-mix(in srgb, var(--ink) 85%, var(--note-${color}))`,
  }
}

/** Hairlines on a coloured card mix a little ink into the note colour, so they stay visible. */
export function noteLine(color: NoteColor): string {
  return color === 'default'
    ? 'var(--line)'
    : `color-mix(in srgb, var(--ink) 12%, var(--note-${color}))`
}

export type NotesView = 'notes' | 'archive' | 'trash' | 'label' | 'search'

/** The IDs of the notes on screen, in the order shown; NotesView provides it for range selection. */
export const NOTE_ORDER: InjectionKey<Ref<string[]>> = Symbol('note order')
