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

/** Hairlines on a coloured card mix a little ink into the note colour, so they stay visible. */
export function noteLine(color: NoteColor): string {
  return color === 'default'
    ? 'var(--line)'
    : `color-mix(in srgb, var(--ink) 12%, var(--note-${color}))`
}

export type NotesView = 'notes' | 'archive' | 'trash'
