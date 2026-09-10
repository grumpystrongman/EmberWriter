import { forwardRef, useEffect, useImperativeHandle, useMemo } from 'react'
import CharacterCount from '@tiptap/extension-character-count'
import Highlight from '@tiptap/extension-highlight'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import Underline from '@tiptap/extension-underline'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { marked } from 'marked'
import TurndownService from 'turndown'

import './editor.css'

export type RichEditorHandle = {
  getSelectedText: () => string
  replaceSelection: (text: string) => void
  insertAtEnd: (text: string) => void
  focus: () => void
}

type Props = {
  markdown: string
  documentKey: string
  disabled?: boolean
  placeholder?: string
  onChange: (markdown: string) => void
}

function htmlFromMarkdown(markdown: string): string {
  return marked.parse(markdown || '', { async: false }) as string
}

export default forwardRef<RichEditorHandle, Props>(function RichTextEditor(
  { markdown, documentKey, disabled = false, placeholder = 'Start writing…', onChange },
  ref,
) {
  const turndown = useMemo(() => {
    const service = new TurndownService({
      headingStyle: 'atx',
      bulletListMarker: '-',
      codeBlockStyle: 'fenced',
      emDelimiter: '*',
      strongDelimiter: '**',
    })
    service.addRule('underline', {
      filter: ['u'],
      replacement(content) {
        return `<u>${content}</u>`
      },
    })
    service.addRule('highlight', {
      filter(node) {
        return node.nodeName === 'MARK'
      },
      replacement(content) {
        return `==${content}==`
      },
    })
    return service
  }, [])

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4] },
      }),
      Underline,
      Highlight,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Placeholder.configure({ placeholder }),
      CharacterCount,
    ],
    content: htmlFromMarkdown(markdown),
    editable: !disabled,
    editorProps: {
      attributes: {
        class: 'prose-editor',
        spellcheck: 'true',
        autocapitalize: 'sentences',
      },
    },
    onUpdate({ editor: current }) {
      const next = turndown.turndown(current.getHTML()).trimEnd() + '\n'
      onChange(next === '\n' ? '' : next)
    },
  })

  useEffect(() => {
    if (!editor) return
    const current = turndown.turndown(editor.getHTML()).trimEnd()
    const incoming = markdown.trimEnd()
    if (current !== incoming) editor.commands.setContent(htmlFromMarkdown(markdown), false)
  }, [documentKey, markdown, editor, turndown])

  useEffect(() => {
    editor?.setEditable(!disabled)
  }, [disabled, editor])

  useImperativeHandle(ref, () => ({
    getSelectedText() {
      if (!editor) return ''
      const { from, to } = editor.state.selection
      if (from === to) return ''
      return editor.state.doc.textBetween(from, to, '\n')
    },
    replaceSelection(text: string) {
      if (!editor) return
      editor.chain().focus().insertContent(text).run()
    },
    insertAtEnd(text: string) {
      if (!editor) return
      const end = editor.state.doc.content.size
      editor.chain().focus().insertContentAt(end, `${end ? '\n\n' : ''}${text}`).run()
    },
    focus() {
      editor?.commands.focus()
    },
  }), [editor])

  if (!editor) return <div className="rich-editor-loading">Opening editor…</div>

  return (
    <div className="rich-editor-shell">
      <div className="editor-toolbar" role="toolbar" aria-label="Formatting">
        <button type="button" onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} title="Undo">↶</button>
        <button type="button" onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} title="Redo">↷</button>
        <span className="toolbar-divider" />
        <button type="button" className={editor.isActive('bold') ? 'active' : ''} onClick={() => editor.chain().focus().toggleBold().run()} title="Bold"><strong>B</strong></button>
        <button type="button" className={editor.isActive('italic') ? 'active' : ''} onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic"><em>I</em></button>
        <button type="button" className={editor.isActive('underline') ? 'active' : ''} onClick={() => editor.chain().focus().toggleUnderline().run()} title="Underline"><u>U</u></button>
        <button type="button" className={editor.isActive('strike') ? 'active' : ''} onClick={() => editor.chain().focus().toggleStrike().run()} title="Strike">S̶</button>
        <button type="button" className={editor.isActive('highlight') ? 'active' : ''} onClick={() => editor.chain().focus().toggleHighlight().run()} title="Highlight">▰</button>
        <span className="toolbar-divider" />
        <button type="button" className={editor.isActive('paragraph') ? 'active' : ''} onClick={() => editor.chain().focus().setParagraph().run()}>P</button>
        {[1, 2, 3].map((level) => (
          <button
            key={level}
            type="button"
            className={editor.isActive('heading', { level }) ? 'active' : ''}
            onClick={() => editor.chain().focus().toggleHeading({ level: level as 1 | 2 | 3 }).run()}
          >H{level}</button>
        ))}
        <span className="toolbar-divider" />
        <button type="button" className={editor.isActive('bulletList') ? 'active' : ''} onClick={() => editor.chain().focus().toggleBulletList().run()} title="Bullets">• List</button>
        <button type="button" className={editor.isActive('orderedList') ? 'active' : ''} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Numbered list">1. List</button>
        <button type="button" className={editor.isActive('blockquote') ? 'active' : ''} onClick={() => editor.chain().focus().toggleBlockquote().run()} title="Block quote">❝</button>
        <button type="button" onClick={() => editor.chain().focus().setHorizontalRule().run()} title="Scene break">* * *</button>
        <span className="toolbar-divider" />
        <button type="button" className={editor.isActive({ textAlign: 'left' }) ? 'active' : ''} onClick={() => editor.chain().focus().setTextAlign('left').run()} title="Align left">≡</button>
        <button type="button" className={editor.isActive({ textAlign: 'center' }) ? 'active' : ''} onClick={() => editor.chain().focus().setTextAlign('center').run()} title="Center">≣</button>
        <button type="button" className={editor.isActive({ textAlign: 'right' }) ? 'active' : ''} onClick={() => editor.chain().focus().setTextAlign('right').run()} title="Align right">≡</button>
        <span className="editor-count">{editor.storage.characterCount.words().toLocaleString()} words</span>
      </div>
      <EditorContent editor={editor} className="editor-scroll" />
    </div>
  )
})
