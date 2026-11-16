import { defineComponent, h, type PropType, type VNode } from 'vue'
import type { components } from '@/api/schema'
import type { RichDoc } from '@/db/schema'

type Text = components['schemas']['Text']
type Inline = Text | components['schemas']['HardBreak']

const URL_PATTERN = /\b(https?:\/\/[^\s<>"]+[^\s<>".,;:!?)\]'])/g

/** Splits text into plain runs and clickable links; links are not stored, only detected (SPEC 4.1). */
function linkify(text: string): (string | VNode)[] {
  const parts: (string | VNode)[] = []
  let last = 0
  for (const match of text.matchAll(URL_PATTERN)) {
    const url = match[0]
    if (match.index > last) parts.push(text.slice(last, match.index))
    parts.push(
      h(
        'a',
        {
          href: url,
          target: '_blank',
          rel: 'noopener noreferrer',
          class: 'text-accent underline-offset-2 hover:underline',
          onClick: (event: Event) => event.stopPropagation(),
        },
        url,
      ),
    )
    last = match.index + url.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

function inline(node: Inline): VNode | (string | VNode)[] {
  if (node.type === 'hardBreak') return h('br')
  let content: VNode | (string | VNode)[] = linkify(node.text)
  for (const mark of node.marks ?? []) {
    const tag = { bold: 'strong', italic: 'em', underline: 'u' }[mark.type]
    content = h(tag, content)
  }
  return content
}

/**
 * Renders a stored document by walking its JSON. Server content is never turned into HTML
 * strings, which keeps the app free of stored XSS (SPEC 4.1).
 */
export default defineComponent({
  name: 'RichTextView',
  props: { doc: { type: Object as PropType<RichDoc>, required: true } },
  setup(props) {
    return () => {
      // Empty paragraphs at the end, as the editor leaves them, would only add blank lines to a card.
      const blocks = [...(props.doc.content ?? [])]
      while (blocks.length && !blocks.at(-1)?.content?.length) blocks.pop()
      return h(
        'div',
        { class: 'rich-text' },
        blocks.map((block) => {
          const children = (block.content ?? []).flatMap((node) => inline(node))
          if (block.type === 'heading') return h(block.attrs.level === 1 ? 'h3' : 'h4', children)
          return h('p', children.length ? children : [h('br')])
        }),
      )
    }
  },
})
