import type { RichDoc } from './schema'

export function emptyDoc(): RichDoc {
  return { type: 'doc', content: [] }
}

/** Blocks become lines and hard breaks line breaks, as on the server (SPEC 4.1). */
export function plainText(doc: RichDoc): string {
  return (doc.content ?? [])
    .map((block) =>
      (block.content ?? []).map((node) => (node.type === 'text' ? node.text : '\n')).join(''),
    )
    .join('\n')
}

export function fromPlainText(text: string): RichDoc {
  if (!text) return emptyDoc()
  return {
    type: 'doc',
    content: text
      .split('\n')
      .map((line) =>
        line
          ? { type: 'paragraph', content: [{ type: 'text', text: line }] }
          : { type: 'paragraph' },
      ),
  }
}
