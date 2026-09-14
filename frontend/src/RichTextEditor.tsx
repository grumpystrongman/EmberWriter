import { forwardRef, lazy, Suspense } from 'react'

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

const RichTextEditorImpl = lazy(() => import('./RichTextEditorImpl'))

export default forwardRef<RichEditorHandle, Props>(function RichTextEditor(props, ref) {
  return (
    <Suspense fallback={<div className="rich-editor-loading">Opening editor…</div>}>
      <RichTextEditorImpl {...props} ref={ref} />
    </Suspense>
  )
})
