import { NotesDatabase } from './schema'

let counter = 0

/** A fresh database per test; fake-indexeddb keeps them in memory. */
export function testDatabase(): NotesDatabase {
  counter += 1
  return new NotesDatabase(`test-${counter}-${Math.random()}`)
}
