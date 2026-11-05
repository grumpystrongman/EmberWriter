/** Local UI review against an ISOLATED synthetic-only EmberWriter backend.
 * Node >=22 and an already-running Chrome --remote-debugging-port=9227.
 * Refuses to capture when the backend exposes non-synthetic/other projects.
 * No external npm packages. Screenshots are ignored by git.
 */
import fs from 'node:fs'
import path from 'node:path'

const api = process.env.EMBER_UX_API || 'http://127.0.0.1:8000'
const appUrl = process.env.EMBER_UX_URL || 'http://127.0.0.1:5173/'
const port = process.env.EMBER_UX_CDP || '9227'
const screenshotRoot = path.resolve('.ux-audit')
const pause = (ms) => new Promise(resolve => setTimeout(resolve, ms))

const response = await fetch(api + '/api/projects')
if (!response.ok) throw new Error('An isolated synthetic backend is required')
const projects = await response.json()
if (!Array.isArray(projects) || projects.length !== 1 ||
    !projects[0].name.startsWith('Synthetic ')) {
  throw new Error('Refusing screenshot capture: only a single synthetic-named fixture project is permitted')
}
const targets = await (await fetch('http://127.0.0.1:' + port + '/json')).json()
const target = targets.find(item => item.type === 'page' && item.url.startsWith(appUrl))
if (!target) throw new Error('Chrome needs an open EmberWriter synthetic dev tab: ' + appUrl)
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
let serial = 0
const outstanding = new Map()
ws.onmessage = (event) => {
  const message = JSON.parse(event.data)
  if (!message.id) return
  const pending = outstanding.get(message.id)
  if (!pending) return
  outstanding.delete(message.id)
  if (message.error) pending.reject(new Error(JSON.stringify(message.error)))
  else pending.resolve(message.result)
}
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++serial
  outstanding.set(id, { resolve, reject })
  ws.send(JSON.stringify({ id, method, params }))
})
const js = async expression => {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (result.exceptionDetails) throw new Error('Browser script failed: ' + JSON.stringify(result.exceptionDetails))
  return result.result.value
}
async function capture(label) {
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  const file = path.join(screenshotRoot, label + '.png')
  fs.writeFileSync(file, Buffer.from(result.data, 'base64'))
  return file
}
function assert(condition, reason) { if (!condition) throw new Error('UX smoke failed: ' + reason) }
async function inspect(width, label) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 850, deviceScaleFactor: 1, mobile: width < 600 })
  await js("localStorage.setItem('emberwriter.workspace','plan'); location.reload()")
  await pause(1800)
  await js("document.querySelector('button.project-card')?.click()")
  await pause(1600)
  await js("([...document.querySelectorAll('.planning-groups button')].find(x=>x.innerText.includes('Write the book')))?.click()")
  await pause(350)
  const plan = await js(`({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    groupCount: document.querySelectorAll('.planning-groups button').length,
    toolCount: document.querySelectorAll('.planning-tool-tabs button').length,
    label: document.querySelector('.planning-tool-tabs button.active')?.innerText,
    topNav: [...document.querySelectorAll('.workspace-nav button')].map(x=>x.innerText.trim()),
    more: document.querySelector('.workspace-more > summary') !== null,
    brandIsButton: document.querySelector('.workspace-brand')?.tagName === 'BUTTON'
  })`)
  assert(plan.width === width && plan.scrollWidth <= width + 1, label + ': Plan horizontal overflow')
  assert(plan.groupCount === 4 && plan.toolCount <= 4, label + ': Plan tools overcrowded')
  assert(plan.more && plan.brandIsButton, label + ': navigation inaccessible')
  assert(width < 600
    ? plan.topNav.join(' ').includes('Publish') && plan.topNav.length === 3
    : plan.topNav.length === 5, label + ': primary navigation is wrong')
  await js("document.querySelector('.workspace-more > summary')?.click()")
  const openMore = await js("({open:document.querySelector('.workspace-more').open,count:document.querySelectorAll('.workspace-more-menu button').length})")
  assert(openMore.open && openMore.count === (width < 600 ? 7 : 5), label + ': advanced workspaces unreachable')
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await pause(80)
  assert(!(await js("document.querySelector('.workspace-more').open")), label + ': Escape must close More')
  await capture(label + '-plan')
  await js("([...document.querySelectorAll('.planning-groups button')].find(x=>x.innerText.includes('Edit & review')))?.click()")
  await pause(350)
  const editor = await js("({toolCount:document.querySelectorAll('.planning-tool-tabs button').length,scrollWidth:document.documentElement.scrollWidth})")
  assert(editor.toolCount === 4 && editor.scrollWidth <= width + 1, label + ': editorial navigation overflow')
  await capture(label + '-editorial')
  if (width === 900) {
    await js("([...document.querySelectorAll('.editorial-board-controls button')].find(x=>x.innerText.includes('Scan entire book')))?.click()")
    await pause(1700)
    const page = await js("({total:document.querySelector('.editorial-board-filterbar [role=status]')?.innerText,cards:document.querySelectorAll('.editorial-board-chapters > article').length,more:!!document.querySelector('.editorial-board-load'),errors:[...document.querySelectorAll('.editorial-board-error')].map(x=>x.innerText)})")
    assert(page.cards === 12 && page.more, 'An extended manuscript must paginate its chapter cards: ' + JSON.stringify(page))
    await js("document.querySelector('.editorial-board-load').click()")
    await pause(140)
    const afterMore = await js("document.querySelectorAll('.editorial-board-chapters > article').length")
    assert(afterMore === 24, 'Load more should render 24 chapters, not the entire book')
    await js("document.querySelector('.editorial-board-filterbar input')?.setAttribute('data-ux-test','1')")
    await js("(() => { const el=document.querySelector('.editorial-board-filterbar input'); const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; setter.call(el,'chapter-027'); el.dispatchEvent(new Event('input',{bubbles:true})); })()")
    await pause(180)
    const narrowed = await js("({count:document.querySelectorAll('.editorial-board-chapters > article').length,text:document.querySelector('.editorial-board-chapters')?.innerText.slice(0,180)})")
    assert(narrowed.count === 1 && narrowed.text.includes('chapter-027'), 'Search must narrow the manuscript: '+ JSON.stringify(narrowed))
    console.log('LARGE_BOOK_EDITORIAL_UX_PASSED', JSON.stringify({page, afterMore, narrowed}))
    await capture(label + '-editorial-search')
  }
  await js("([...document.querySelectorAll('.workspace-nav button')].find(x=>x.innerText.includes('Publish')))?.click()")
  await pause(700)
  const publish = await js("({tabs:document.querySelectorAll('.publish-workflow-nav button').length,preflight:document.querySelectorAll('.production-preflight').length,audio:document.querySelectorAll('.audiobook-panel').length,scrollWidth:document.documentElement.scrollWidth})")
  console.log('PUBLISH_CHECK', label, JSON.stringify(publish))
  assert(publish.tabs === 6 && publish.preflight === 1 && publish.audio === 0, label + ': publishing stages not isolated')
  assert(publish.scrollWidth <= width + 1, label + ': publishing page horizontal overflow')
  await capture(label + '-publish')
  await js("([...document.querySelectorAll('.publish-workflow-nav button')].find(x=>x.innerText.includes('Book files')))?.click()")
  await pause(500)
  const files = await js("({preflight:document.querySelectorAll('.production-preflight').length,scrollWidth:document.documentElement.scrollWidth})")
  assert(files.preflight === 0 && files.scrollWidth <= width + 1, label + ': book files stage overflow')
  await capture(label + '-book-files')
  await js("([...document.querySelectorAll('.publish-workflow-nav button')].find(x=>x.innerText.includes('Audiobook')))?.click()")
  await pause(900)
  const audiobook = await js("({visible:!!document.querySelector('.audiobook-heading'),rate:!!document.querySelector('#audio-rate'),qc:[...document.querySelectorAll('.audiobook-panel button')].some(x=>x.innerText.includes('Check audio readiness')),tabVisible:(()=>{const nav=document.querySelector('.publish-workflow-nav');const active=nav?.querySelector('button.active');if(!nav||!active)return false;const n=nav.getBoundingClientRect(),b=active.getBoundingClientRect();return b.left>=n.left-2&&b.right<=n.right+2})(),overflow:document.documentElement.scrollWidth-innerWidth})")
  assert(audiobook.visible && audiobook.rate && audiobook.qc && audiobook.tabVisible && audiobook.overflow <= 1,
    label + ': audiobook workspace must fit and expose pacing/QC')
  const direction = await js("({count:document.querySelectorAll('.audiobook-direction').length,collapsed:[...document.querySelectorAll('.audiobook-direction')].every(x=>!x.open)})")
  assert(direction.count === 2 && direction.collapsed, label + ': narration direction must be opt-in and collapsed')
  await capture(label + '-audiobook')
  await js("document.querySelector('.audiobook-direction > summary')?.click()")
  await pause(200)
  const expanded = await js("({dictionary:!!document.querySelector('.audiobook-editor-row input'),overflow:document.documentElement.scrollWidth-innerWidth})")
  assert(expanded.dictionary && expanded.overflow <= 1, label + ': expanded pronunciation controls overflow')
  await capture(label + '-audio-direction')
  await js("([...document.querySelectorAll('.audiobook-panel button')].find(x=>x.innerText.includes('Check audio readiness')))?.click()")
  await pause(950)
  const ready = await js("({pass:!!document.querySelector('.audiobook-quality h3')?.innerText.includes('passed'),mastering:[...document.querySelectorAll('.audiobook-direction > summary')].some(x=>x.innerText.includes('loudness'))})")
  assert(ready.pass && ready.mastering, label + ': verified synthetic chapter must expose optional mastering')
  await js("([...document.querySelectorAll('.audiobook-direction > summary')].find(x=>x.innerText.includes('loudness')))?.click()")
  await pause(200)
  assert((await js("document.documentElement.scrollWidth-innerWidth")) <= 1, label + ': expanded mastering panel overflow')
  if (width === 900) {
    await js("([...document.querySelectorAll('.audiobook-panel button')].find(x=>x.innerText.includes('Analyze audiobook loudness')))?.click()")
    await pause(2500)
    const metrics = await js("({reported:!!document.querySelector('.audiobook-mastering'),target:document.querySelector('.audiobook-mastering > strong')?.innerText,error:document.querySelector('.audiobook-alert')?.innerText})")
    assert(metrics.reported && metrics.target.includes('LUFS'), 'Measured mastering results missing: '+JSON.stringify(metrics))
    console.log('REAL_AUDIO_MASTERING_UI_PASSED', JSON.stringify(metrics))
    await capture(label + '-loudness-measured')
  }
  await capture(label + '-audio-mastering')
  console.log(JSON.stringify({ viewport: width, plan, editor, publish, files, audiobook, direction, expanded, ready }))
}
fs.mkdirSync(screenshotRoot, { recursive: true })
try {
  await send('Page.enable')
  for (const width of [1440, 900, 390]) await inspect(width, String(width))
  console.log('UX_VISUAL_SMOKE_PASSED screenshots=' + screenshotRoot)
} finally {
  ws.close()
}
