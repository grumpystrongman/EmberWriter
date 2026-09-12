import { saveInbox, type CaptureItem, type ProjectSummary } from './capture-store'

type Props = { project: ProjectSummary; items: CaptureItem[]; onItems: (items: CaptureItem[]) => void }

export default function CaptureInbox({ project, items, onItems }: Props) {
  const active = items.filter((item) => item.status !== 'archived')

  async function archive(id: string) {
    const next = items.map((item) => item.id === id ? { ...item, status: 'archived' as const, updated_at: new Date().toISOString() } : item)
    onItems(next)
    await saveInbox(project, next)
  }

  return <div className="capture-inbox">
    <div className="capture-inbox-head"><h3>Idea Inbox</h3><span>{active.length} active</span></div>
    {active.length === 0 && <div className="capture-empty">No ideas captured yet. Speak first; organize later.</div>}
    {active.slice(0, 25).map((item) => <article key={item.id}>
      <div><span>{item.kind}</span><small>{new Date(item.created_at).toLocaleString()}</small></div>
      <p>{item.text}</p>
      <footer><span>{item.destination === 'inbox' ? 'Inbox' : `Routed: ${item.destination.replace('_', ' ')}`}</span><button type="button" onClick={() => void archive(item.id)}>Archive</button></footer>
    </article>)}
  </div>
}
