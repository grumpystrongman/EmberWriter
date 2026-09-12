import type { ProjectSummary } from './capture-store'
import { openProjectPath } from './write-workspace-store'

type Props = {
  project: ProjectSummary
  activePath: string
  tabs: string[]
  onTabs: (tabs: string[]) => void
  onSplit: () => void
  onSearch: () => void
}

function label(path: string) {
  return path.split('/').at(-1)?.replace(/\.(md|txt)$/i, '') || path
}

export default function WriteTabsBar({ project, activePath, tabs, onTabs, onSplit, onSearch }: Props) {
  async function activate(path: string) {
    await openProjectPath(project.slug, path)
  }

  function close(path: string) {
    const next = tabs.filter((item) => item !== path)
    onTabs(next)
    if (path === activePath && next.length) void activate(next[next.length - 1])
  }

  return <div className="write-tabs-bar">
    <div className="write-tabs-scroll">
      {tabs.map((path) => <div key={path} className={`write-tab ${path === activePath ? 'active' : ''}`}>
        <button type="button" title={path} onClick={() => void activate(path)}>{label(path)}</button>
        <button type="button" className="write-tab-close" aria-label={`Close ${label(path)}`} onClick={() => close(path)}>×</button>
      </div>)}
    </div>
    <div className="write-tabs-actions"><button type="button" onClick={onSearch}>⌕ Search</button><button type="button" onClick={onSplit}>◫ Split</button></div>
  </div>
}
