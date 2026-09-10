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

import ReviewPanel, { type ReviewAnnotation } from './ReviewPanel'
import './editor.css'

export type RichEditorHandle = {
  getSelectedText: () => string
  replaceSelection: (text: string) => void
  insertAtEnd: (text: string) => void
  findAndSelect: (text: string) => boolean
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

function outerHtml(node: Node): string {
  return node instanceof HTMLElement ? node.outerHTML : node.textContent || ''
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
    service.addRule('alignedBlocks', {
      filter(node) {
        if (!(node instanceof HTMLElement)) return false
        return ['P', 'H1', 'H2', 'H3', 'H4'].includes(node.nodeName) && Boolean(node.style.textAlign)
      },
      replacement(_content, node) {
        return `\n\n${outerHtml(node)}\n\n`
      },
    })
    service.addRule('underline', {
      filter: ['u'],
      replacement(_content, node) {
        return outerHtml(node)
      },
    })
    service.addRule('highlight', {
      filter(node) {
        return node.nodeName === 'MARK'
      },
      replacement(_content, node) {
        return outerHtml(node)
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

  function selectedText() {
    if (!editor) return ''
    const { from, to } = editor.state.selection
    if (from === to) return ''
    return editor.state.doc.textBetween(from, to, '\n')
  }

  function selectText(text: string) {
    if (!editor || !text.trim()) return false
    const root = editor.view.dom
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    const segments: { node: Node; start: number; end: number }[] = []
    let haystack = ''
    let currentNode = walker.nextNode()
    while (currentNode) {
      const value = currentNode.textContent || ''
      const start = haystack.length
      haystack += value
      segments.push({ node: currentNode, start, end: haystack.length })
      currentNode = walker.nextNode()
    }

    const candidates = [
      text.trim(),
      text.trim().split(/\s+/).slice(0, 8).join(' '),
      text.trim().split(/\s+/).slice(0, 4).join(' '),
    ].filter((value, index, items) => value.length >= 2 && items.indexOf(value) === index)
    let matchStart = -1
    let matchText = ''
    for (const candidate of candidates) {
      matchStart = haystack.indexOf(candidate)
      if (matchStart >= 0) {
        matchText = candidate
        break
      }
    }
    if (matchStart < 0) return false
    const matchEnd = matchStart + matchText.length
    const startSegment = segments.find((segment) => matchStart >= segment.start && matchStart <= segment.end)
    const endSegment = segments.find((segment) => matchEnd >= segment.start && matchEnd <= segment.end)
    if (!startSegment || !endSegment) return false

    const startOffset = Math.max(0, matchStart - startSegment.start)
    const endOffset = Math.max(0, matchEnd - endSegment.start)
    const from = editor.view.posAtDOM(startSegment.node, startOffset)
    const to = editor.view.posAtDOM(endSegment.node, endOffset)
    editor.chain().focus().setTextSelection({ from, to }).scrollIntoView().run()
    return true
  }

  useImperativeHandle(ref, () => ({
    getSelectedText: selectedText,
    replaceSelection(text: string) {
      if (!editor) return
      editor.chain().focus().insertContent(htmlFromMarkdown(text)).run()
    },
    insertAtEnd(text: string) {
      if (!editor) return
      const end = editor.state.doc.content.size
      editor.chain().focus().insertContentAt(end, htmlFromMarkdown(text)).run()
    },
    findAndSelect: selectText,
    focus() {
      editor?.commands.focus()
    },
  }), [editor])

  if (!editor) return <div className="rich-editor-loading">Opening editor…</div>

  const separator = documentKey.indexOf(':')
  const projectSlug = separator >= 0 ? documentKey.slice(0, separator) : ''
  const activePath = separator >= 0 ? documentKey.slice(separator + 1) : ''

  function openAnnotation(annotation: ReviewAnnotation) {
    if (annotation.stale) return
    selectText(annotation.anchor_text)
  }

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
      {projectSlug && activePath && (
        <ReviewPanel
          apiBase="http://127.0.0.1:8000/api"
          slug={projectSlug}
          activePath={activePath}
          disabled={disabled}
          refreshToken={0}
          getSelectedText={selectedText}
          onOpen={openAnnotation}
        />
      )}
    </div>
  )
})
