const API = 'http://127.0.0.1:8000/api'
export const INBOX_PATH = 'planning/idea-inbox.json'

export type CaptureKind = 'idea' | 'dialogue' | 'character' | 'world' | 'plot' | 'scene' | 'research' | 'todo'
export type Destination = 'inbox' | 'beat_sheet' | 'world' | 'character' | 'scene' | 'project_note'
export type ProjectSummary = { slug: string; name: string; description: string }
export type CaptureItem = {
  id: string
  text: string
  kind: CaptureKind
  source: 'typed' | 'speech'
  destination: Destination
  context_path: string
  status: 'open' | 'routed' | 'archived'
  created_at: string
  updated_at: string
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export function activeProjectName() {
  return document.querySelector<HTMLElement>('.project-card.active strong')?.textContent?.trim() || ''
}

export function activeDocumentPath() {
  const value = document.querySelector<HTMLElement>('.editor-header h1')?.textContent?.trim() || ''
  return value === 'Select a file' ? '' : value
}

export async function resolveActiveProject(): Promise<ProjectSummary | null> {
  const name = activeProjectName()
  if (!name) return null
  const projects = await request<ProjectSummary[]>(`${API}/projects`)
  return projects.find((item) => item.name === name) || null
}

export async function loadInbox(project: ProjectSummary): Promise<CaptureItem[]> {
  const response = await fetch(`${API}/projects/${project.slug}/file?path=${encodeURIComponent(INBOX_PATH)}`)
  if (response.status === 404) return []
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  const body = await response.json() as { content: string }
  const parsed = JSON.parse(body.content) as { ideas?: CaptureItem[] }
  return Array.isArray(parsed.ideas) ? parsed.ideas : []
}

export async function saveInbox(project: ProjectSummary, ideas: CaptureItem[]) {
  await request(`${API}/projects/${project.slug}/file?path=${encodeURIComponent(INBOX_PATH)}`, {
    method: 'PUT',
    body: JSON.stringify({ content: JSON.stringify({ schema_version: 1, ideas }, null, 2) }),
  })
}

async function readText(project: ProjectSummary, path: string) {
  const response = await fetch(`${API}/projects/${project.slug}/file?path=${encodeURIComponent(path)}`)
  if (response.status === 404) return ''
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  const body = await response.json() as { content: string }
  return body.content
}

async function writeText(project: ProjectSummary, path: string, content: string) {
  await request(`${API}/projects/${project.slug}/file?path=${encodeURIComponent(path)}`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  })
}

function safeTitle(text: string) {
  return text.trim().slice(0, 48).replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'captured-idea'
}

export async function routeCapture(project: ProjectSummary, item: CaptureItem) {
  if (item.destination === 'inbox') return
  if (item.destination === 'beat_sheet') {
    const path = 'planning/beat-sheet.md'
    const existing = await readText(project, path)
    const heading = existing.includes('## Captured Ideas') ? '' : `${existing.trim() ? '\n\n' : ''}## Captured Ideas\n`
    await writeText(project, path, `${existing.trimEnd()}${heading}\n- [${item.kind}] ${item.text}\n`)
    return
  }
  const folder = {
    world: 'world',
    character: 'characters',
    scene: 'scenes',
    project_note: 'planning/notes',
  }[item.destination]
  if (!folder) return
  const stamp = item.created_at.slice(0, 10)
  const path = `${folder}/${stamp}-${safeTitle(item.text)}-${item.id.slice(-5)}.md`
  const context = item.context_path ? `\nContext document: ${item.context_path}\n` : ''
  await writeText(project, path, `# Captured ${item.kind}\n\n${item.text}\n${context}\nCaptured: ${item.created_at}\nSource: ${item.source}\n`)
}

export function createCapture(text: string, kind: CaptureKind, destination: Destination, source: 'typed' | 'speech'): CaptureItem {
  const stamp = new Date().toISOString()
  return {
    id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`,
    text: text.trim(),
    kind,
    source,
    destination,
    context_path: activeDocumentPath(),
    status: destination === 'inbox' ? 'open' : 'routed',
    created_at: stamp,
    updated_at: stamp,
  }
}
