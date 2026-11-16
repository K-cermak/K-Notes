import type { Extensions } from '@tiptap/core'
import Bold from '@tiptap/extension-bold'
import Document from '@tiptap/extension-document'
import HardBreak from '@tiptap/extension-hard-break'
import Heading from '@tiptap/extension-heading'
import Italic from '@tiptap/extension-italic'
import Paragraph from '@tiptap/extension-paragraph'
import Text from '@tiptap/extension-text'
import Underline from '@tiptap/extension-underline'
import { Placeholder, UndoRedo } from '@tiptap/extensions'

/**
 * Exactly the schema the server accepts (SPEC 4.1). Pasted content outside it, such as lists,
 * links or images, is reduced to these nodes by ProseMirror's schema.
 */
export function noteExtensions(placeholder: string): Extensions {
  return [
    Document,
    Paragraph,
    Text,
    Heading.configure({ levels: [1, 2] }),
    HardBreak,
    Bold,
    Italic,
    Underline,
    UndoRedo,
    Placeholder.configure({ placeholder }),
  ]
}
