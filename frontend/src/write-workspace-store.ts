const API = 'http://127.0.0.1:8000/api'

type ProjectSummary = { slug: string; name: string; description: string }
type BinderNode = { id: string; title: string; parent_id: string | null; path: string | null }
type BinderState = { nodes: BinderNode[] }

function clean(value: string | null | undefined) {
  return (value || '').replace(/\s+/g, ' ').trim()
}

export function activePath() {
  const value = clean(document.querySelector<HTMLElement>('.editor-header h1')?.textContent)
  return value === 'Select a file' ? '' : value
}

export async function activeProject(): Promise<ProjectSummary | null> {
  const name = clean(document.querySelector<HTMLElement>('.project-card.active strong')?.textContent)
  if (!name) return null
  const response = await fetch(`${API}/projects`)
  if (!response.ok) return null
  const projects = await response.json() as ProjectSummary[]
  return projects.find((item) => item.name === name) || null
}

function buttonFor(title: string) {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.binder-node-button'))
    .find((button) => clean(button.querySelector('strong')?.textContent) === title) || null
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export async function openProjectPath(slug: string, path: string) {
  const response = await fetch(`${API}/projects/${slug}/binder`)
  if (!response.ok) return false
  const binder = await response.json() as BinderState
  const node = binder.nodes.find((item) => item.path === path)
  if (!node) return false
  const nodes = new Map(binder.nodes.map((item) => [item.id, item]))
  const parents: BinderNode[] = []
  let parentId = node.parent_id
  while (parentId) {
    const parent = nodes.get(parentId)
    if (!parent) break
    parents.unshift(parent)
    parentId = parent.parent_id
  }
  for (const parent of parents) {
    const row = buttonFor(parent.title)?.closest('.binder-row')
    const disclosure = row?.querySelector<HTMLButtonElement>('.binder-disclosure')
    if (disclosure && clean(disclosure.textContent) === '›') {
      disclosure.click()
      await sleep(35)
    }
  }
  buttonFor(node.title)?.click()
  return true
}

export async function projectFiles(slug: string) {
  const response = await fetch(`${API}/projects/${slug}`)
  if (!response.ok) return [] as string[]
  const detail = await response.json() as { files: string[] }
  return detail.files
}

export async function readProjectFile(slug: string, path: string) {
  const response = await fetch(`${API}/projects/${slug}/file?path=${encodeURIComponent(path)}`)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return (await response.json() as { content: string }).content
}

export async function saveProjectFile(slug: string, path: string, content: string) {
  const response = await fetch(`${API}/projects/${slug}/file?path=${encodeURIComponent(path)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
}
