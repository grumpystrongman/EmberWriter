import { forwardRef, useEffect, useImperativeHandle, useMemo, useState } from 'react'
import CharacterCount from '@tiptap/extension-character-count'
import Highlight from '@tiptap/extension-highlight'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import Underline from '@tiptap/extension-underline'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { marked } from 'marked'
import TurndownService from 'turndown'

import { diagnoseText, LiveDiagnostics } from './LiveDiagnostics'
import ReviewPanel, { type ReviewAnnotation } from './ReviewPanel'
import SprintPanel from './SprintPanel'
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

type EditorialApplyDetail = {
  path: string
  original: string
  replacement: string
  respond?: (applied: boolean) => void
}

function htmlFromMarkdown(markdown: string): string {
  return marked.parse(markdown || '', { async: false }) as string
}

function inlineHtmlFromMarkdown(markdown: string): string {
  const html = htmlFromMarkdown(markdown).trim()
  const singleParagraph = html.match(/^<p>([\s\S]*)<\/p>$/)
  return singleParagraph ? singleParagraph[1] : html
}

function outerHtml(node: Node): string {
  return node instanceof HTMLElement ? node.outerHTML : node.textContent || ''
}

function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

export default forwardRef<RichEditorHandle, Props>(function RichTextEditor(
  { markdown, documentKey, disabled = false, placeholder = 'Start writing…', onChange },
  ref,
) {
  const [findOpen, setFindOpen] = useState(false)
  const [findText, setFindText] = useState('')
  const [replaceText, setReplaceText] = useState('')
  const [findStatus, setFindStatus] = useState('')
  const [selectionWords, setSelectionWords] = useState(0)
  const [documentWords, setDocumentWords] = useState(() => wordCount(markdown))
  const [liveIssueCount, setLiveIssueCount] = useState(0)
  const [spellcheckEnabled, setSpellcheckEnabled] = useState(() => localStorage.getItem('emberwriter.spellcheck') !== 'false')
  const [liveDiagnosticsEnabled, setLiveDiagnosticsEnabled] = useState(() => localStorage.getItem('emberwriter.liveDiagnostics') !== 'false')
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
      LiveDiagnostics,
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
    onCreate({ editor: current }) {
      setDocumentWords(current.storage.characterCount.words())
      setLiveIssueCount(diagnoseText(current.state.doc.textContent).length)
    },
    onUpdate({ editor: current }) {
      const next = turndown.turndown(current.getHTML()).trimEnd() + '\n'
      setDocumentWords(current.storage.characterCount.words())
      setLiveIssueCount(diagnoseText(current.state.doc.textContent).length)
      onChange(next === '\n' ? '' : next)
    },
    onSelectionUpdate({ editor: current }) {
      const { from, to } = current.state.selection
      setSelectionWords(from === to ? 0 : wordCount(current.state.doc.textBetween(from, to, ' ')))
    },
  })

  useEffect(() => {
    if (!editor) return
    const current = turndown.turndown(editor.getHTML()).trimEnd()
    const incoming = markdown.trimEnd()
    if (current !== incoming) editor.commands.setContent(htmlFromMarkdown(markdown), false)
    setDocumentWords(editor.storage.characterCount.words())
    setLiveIssueCount(diagnoseText(editor.state.doc.textContent).length)
  }, [documentKey, markdown, editor, turndown])

  useEffect(() => {
    editor?.setEditable(!disabled)
  }, [disabled, editor])

  useEffect(() => {
    localStorage.setItem('emberwriter.spellcheck', String(spellcheckEnabled))
    if (editor) editor.view.dom.setAttribute('spellcheck', spellcheckEnabled ? 'true' : 'false')
  }, [spellcheckEnabled, editor])

  useEffect(() => {
    localStorage.setItem('emberwriter.liveDiagnostics', String(liveDiagnosticsEnabled))
  }, [liveDiagnosticsEnabled])

  const separator = documentKey.indexOf(':')
  const projectSlug = separator >= 0 ? documentKey.slice(0, separator) : ''
  const activePath = separator >= 0 ? documentKey.slice(separator + 1) : ''

  function selectedText() {
    if (!editor) return ''
    const { from, to } = editor.state.selection
    if (from === to) return ''
    return editor.state.doc.textBetween(from, to, '\n')
  }

  function textRanges(text: string) {
    if (!editor || !text.trim()) return [] as { from: number; to: number }[]
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

    const needle = text.trim()
    const lowerHaystack = haystack.toLocaleLowerCase()
    const lowerNeedle = needle.toLocaleLowerCase()
    const ranges: { from: number; to: number }[] = []
    let cursor = 0
    while (cursor <= lowerHaystack.length - lowerNeedle.length) {
      const matchStart = lowerHaystack.indexOf(lowerNeedle, cursor)
      if (matchStart < 0) break
      const matchEnd = matchStart + needle.length
      const startSegment = segments.find((segment) => matchStart >= segment.start && matchStart < segment.end)
      const endSegment = segments.find((segment) => matchEnd > segment.start && matchEnd <= segment.end)
      if (startSegment && endSegment) {
        const startOffset = Math.max(0, matchStart - startSegment.start)
        const endOffset = Math.max(0, matchEnd - endSegment.start)
        try {
          const from = editor.view.posAtDOM(startSegment.node, startOffset)
          const to = editor.view.posAtDOM(endSegment.node, endOffset)
          if (to > from) ranges.push({ from, to })
        } catch {
          // Ignore DOM positions that cannot be mapped back into the editor document.
        }
      }
      cursor = matchStart + Math.max(1, needle.length)
    }
    return ranges
  }

  function selectText(text: string, next = false) {
    if (!editor || !text.trim()) return false
    const candidates = [
      text.trim(),
      text.trim().split(/\s+/).slice(0, 12).join(' '),
      text.trim().split(/\s+/).slice(0, 8).join(' '),
      text.trim().split(/\s+/).slice(0, 4).join(' '),
    ].filter((value, index, items) => value.length >= 2 && items.indexOf(value) === index)

    for (const candidate of candidates) {
      const ranges = textRanges(candidate)
      if (!ranges.length) continue
      let target = ranges[0]
      if (next) {
        const current = editor.state.selection.from
        target = ranges.find((range) => range.from > current) || ranges[0]
      }
      editor.chain().focus().setTextSelection(target).scrollIntoView().run()
      return true
    }
    return false
  }

  function findNext() {
    if (!findText.trim()) return
    const ranges = textRanges(findText)
    if (!ranges.length) {
      setFindStatus('No matches')
      return
    }
    const selected = selectText(findText, true)
    setFindStatus(selected ? `${ranges.length} match${ranges.length === 1 ? '' : 'es'}` : 'No matches')
  }

  function replaceCurrent() {
    if (!editor || !findText.trim()) return
    const current = selectedText()
    if (current.toLocaleLowerCase() !== findText.trim().toLocaleLowerCase()) {
      findNext()
      return
    }
    editor.chain().focus().insertContent(inlineHtmlFromMarkdown(replaceText)).run()
    setFindStatus('Replaced 1 match')
    window.setTimeout(findNext, 0)
  }

  function replaceAll() {
    if (!editor || !findText.trim()) return
    const query = findText.trim().toLocaleLowerCase()
    const ranges: { from: number; to: number }[] = []
    editor.state.doc.descendants((node, pos) => {
      if (!node.isText || !node.text) return
      const lower = node.text.toLocaleLowerCase()
      let cursor = 0
      while (cursor <= lower.length - query.length) {
        const index = lower.indexOf(query, cursor)
        if (index < 0) break
        ranges.push({ from: pos + index, to: pos + index + query.length })
        cursor = index + Math.max(1, query.length)
      }
    })
    if (!ranges.length) {
      setFindStatus('No matches')
      return
    }
    const transaction = editor.state.tr
    for (const range of [...ranges].reverse()) {
      transaction.insertText(replaceText, range.from, range.to)
    }
    editor.view.dispatch(transaction)
    editor.commands.focus()
    setFindStatus(`Replaced ${ranges.length} match${ranges.length === 1 ? '' : 'es'}`)
  }

  useEffect(() => {
    function applyEditorialFix(event: Event) {
      const custom = event as CustomEvent<EditorialApplyDetail>
      const detail = custom.detail
      if (!detail || detail.path !== activePath || !editor) return
      const selected = selectText(detail.original)
      if (!selected) {
        detail.respond?.(false)
        return
      }
      editor.chain().focus().insertContent(inlineHtmlFromMarkdown(detail.replacement)).run()
      detail.respond?.(true)
    }
    window.addEventListener('emberwriter:apply-editorial-fix', applyEditorialFix)
    return () => window.removeEventListener('emberwriter:apply-editorial-fix', applyEditorialFix)
  }, [editor, activePath])

  useImperativeHandle(ref, () => ({
    getSelectedText: selectedText,
    replaceSelection(text: string) {
      if (!editor) return
      editor.chain().focus().insertContent(inlineHtmlFromMarkdown(text)).run()
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

  function openAnnotation(annotation: ReviewAnnotation) {
    if (annotation.stale) return
    selectText(annotation.anchor_text)
  }

  return (
    <div className={`rich-editor-shell ${liveDiagnosticsEnabled ? '' : 'diagnostics-off'}`}>
      <div className="editor-toolbar" role="toolbar" aria-label="Formatting">
        <button type="button" onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} title="Undo">↶</button>
        <button type="button" onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} title="Redo">↷</button>
        <button type="button" className={findOpen ? 'active' : ''} onClick={() => setFindOpen((value) => !value)} title="Find and replace">⌕</button>
        <button type="button" className={spellcheckEnabled ? 'active' : ''} onClick={() => setSpellcheckEnabled((value) => !value)} title="Browser spelling suggestions">ABC</button>
        <button type="button" className={liveDiagnosticsEnabled ? 'active' : ''} onClick={() => setLiveDiagnosticsEnabled((value) => !value)} title="Live Ember prose diagnostics">Style {liveIssueCount}</button>
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
        <span className="editor-count">
          {selectionWords > 0 ? `${selectionWords.toLocaleString()} selected · ` : ''}
          {documentWords.toLocaleString()} words · {editor.storage.characterCount.characters().toLocaleString()} chars
        </span>
      </div>
      {findOpen && (
        <div className="editor-findbar">
          <input value={findText} onChange={(event) => { setFindText(event.target.value); setFindStatus('') }} placeholder="Find" onKeyDown={(event) => { if (event.key === 'Enter') findNext() }} autoFocus />
          <input value={replaceText} onChange={(event) => setReplaceText(event.target.value)} placeholder="Replace with" />
          <button type="button" onClick={findNext} disabled={!findText.trim()}>Next</button>
          <button type="button" onClick={replaceCurrent} disabled={!findText.trim() || disabled}>Replace</button>
          <button type="button" onClick={replaceAll} disabled={!findText.trim() || disabled}>Replace all</button>
          <small>{findStatus}</small>
          <button type="button" className="quiet" onClick={() => setFindOpen(false)} aria-label="Close find and replace">×</button>
        </div>
      )}
      {projectSlug && activePath && (
        <SprintPanel
          apiBase="http://127.0.0.1:8000/api"
          slug={projectSlug}
          path={activePath}
          wordCount={documentWords}
          disabled={disabled}
        />
      )}
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
