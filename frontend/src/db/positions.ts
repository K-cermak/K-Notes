import { generateNKeysBetween } from 'fractional-indexing'

/**
 * Keys for n rows inserted before positions[index] in an ascending list of positions (SPEC 4.2).
 * Rows from two devices can share a position, and no key fits between equal keys, so the upper
 * bound is the first position after the gap that is above the lower one.
 */
export function insertKeys(positions: string[], index: number, n = 1): string[] {
  const before = positions[index - 1] ?? null
  const after = positions.slice(index).find((p) => before === null || p > before) ?? null
  return generateNKeysBetween(before, after, n)
}
