import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Decoration, DecorationSet } from '@tiptap/pm/view'

export type LiveDiagnostic = {
  from: number
  to: number
  kind: 'error' | 'warning' | 'info'
  message: string
}

const ADVERB_EXCEPTIONS = new Set([
  'apply', 'belly', 'early', 'family', 'friendly', 'holy', 'jelly', 'likely', 'lonely', 'lovely',
  'only', 'reply', 'silly', 'supply', 'ugly',
])

const FILLERS = new Set([
  'actually', 'basically', 'just', 'literally', 'quite', 'rather', 'really', 'simply', 'somewhat',
  'suddenly', 'very',
])

const REDUNDANCIES: Array<[RegExp, string]> = [
  [/\bin order to\b/gi, 'Consider “to” unless the longer phrase is intentional.'],
  [/\bbegan to\b/gi, 'Consider using the direct verb when the beginning is not important.'],
  [/\bstarted to\b/gi, 'Consider using the direct verb when the start itself is not important.'],
  [/\beach and every\b/gi, 'Usually “each” or “every” is enough.'],
  [/\bat this point in time\b/gi, 'Consider “now” if the longer phrase adds no voice.'],
  [/\bvery unique\b/gi, '“Unique” usually does not need an intensifier.'],
]

const WORD_RE = /\b[A-Za-z][A-Za-z’'-]*\b/g

export function diagnoseText(text: string): LiveDiagnostic[] {
  const issues: LiveDiagnostic[] = []

  const repeated = /\b([A-Za-z][A-Za-z’'-]*)\s+\1\b/gi
  for (const match of text.matchAll(repeated)) {
    if (match.index === undefined) continue
    issues.push({
      from: match.index,
      to: match.index + match[0].length,
      kind: 'error',
      message: `Repeated word: “${match[1]}”.`,
    })
  }

  const punctuation = /(?:!{2,}|\?{2,}|\.{4,}|\s+[,.!?;:])/g
  for (const match of text.matchAll(punctuation)) {
    if (match.index === undefined) continue
    issues.push({
      from: match.index,
      to: match.index + match[0].length,
      kind: 'error',
      message: 'Check this punctuation.',
    })
  }

  for (const match of text.matchAll(WORD_RE)) {
    if (match.index === undefined) continue
    const word = match[0].toLocaleLowerCase()
    if (FILLERS.has(word)) {
      issues.push({
        from: match.index,
        to: match.index + match[0].length,
        kind: 'info',
        message: `Possible filler word: “${match[0]}”. Keep it when voice or emphasis needs it.`,
      })
    }
    if (word.endsWith('ly') && word.length > 4 && !ADVERB_EXCEPTIONS.has(word)) {
      issues.push({
        from: match.index,
        to: match.index + match[0].length,
        kind: 'warning',
        message: `Possible adverb: “${match[0]}”. Check whether the verb or beat can carry the meaning more precisely.`,
      })
    }
  }

  for (const [pattern, message] of REDUNDANCIES) {
    pattern.lastIndex = 0
    for (const match of text.matchAll(pattern)) {
      if (match.index === undefined) continue
      issues.push({
        from: match.index,
        to: match.index + match[0].length,
        kind: 'warning',
        message,
      })
    }
  }

  return issues.sort((a, b) => a.from - b.from || a.to - b.to)
}

function decorationsForDocument(doc: Parameters<typeof DecorationSet.create>[0]) {
  const decorations: Decoration[] = []
  doc.descendants((node, pos) => {
    if (!node.isText || !node.text) return
    for (const issue of diagnoseText(node.text)) {
      decorations.push(
        Decoration.inline(pos + issue.from, pos + issue.to, {
          class: `ember-diagnostic ember-diagnostic-${issue.kind}`,
          title: issue.message,
          'data-ember-diagnostic': issue.message,
        }),
      )
    }
  })
  return DecorationSet.create(doc, decorations)
}

const liveDiagnosticsKey = new PluginKey<DecorationSet>('emberLiveDiagnostics')

export const LiveDiagnostics = Extension.create({
  name: 'emberLiveDiagnostics',
  addProseMirrorPlugins() {
    return [
      new Plugin<DecorationSet>({
        key: liveDiagnosticsKey,
        state: {
          init: (_, state) => decorationsForDocument(state.doc),
          apply(transaction, previous, _oldState, newState) {
            if (transaction.docChanged) return decorationsForDocument(newState.doc)
            return previous.map(transaction.mapping, transaction.doc)
          },
        },
        props: {
          decorations(state) {
            return liveDiagnosticsKey.getState(state) ?? null
          },
        },
      }),
    ]
  },
})
