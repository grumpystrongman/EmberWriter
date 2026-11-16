import {useEffect,useMemo,useRef,useState} from 'react'
import type {KeyboardEvent,ReactNode} from 'react'
import './review-queue.css'

export type QueueRow={key:string;title:string;subtitle:string;preview:string;
 status?:string;meta?:string;searchText?:string}
type Props={
 title:string;description:string;rows:QueueRow[];emptyText:string;
 detail:(row:QueueRow)=>ReactNode;toolbar?:ReactNode;footer?:ReactNode;
 loading?:boolean;pageLabel?:string;selectedKey?:string|null;
 onSelectionChange?:(key:string)=>void;statusOptions?:string[]
}
export default function ReviewQueue({title,description,rows,emptyText,detail,toolbar,footer,
 loading=false,pageLabel,selectedKey,onSelectionChange,statusOptions}:Props){
 const [localKey,setLocalKey]=useState<string|null>(null)
 const [search,setSearch]=useState('')
 const [status,setStatus]=useState('all')
 const [order,setOrder]=useState<'source'|'title'|'status'>('source')
 const [comfortable,setComfortable]=useState(false)
 const [detailOpen,setDetailOpen]=useState(false)
 const notified=useRef<string|null>(null)
 const options=statusOptions||Array.from(new Set(rows.map(x=>x.status||'').filter(Boolean)))
 const visible=useMemo(()=>{
  const result=rows.filter(row=>{
   if(status!=='all'&&row.status!==status)return false
   const needle=search.trim().toLocaleLowerCase()
   return !needle||[row.title,row.subtitle,row.preview,row.meta,row.searchText].join(' ').toLocaleLowerCase().includes(needle)
  })
  if(order==='title')result.sort((a,b)=>a.title.localeCompare(b.title))
  if(order==='status')result.sort((a,b)=>(a.status||'').localeCompare(b.status||''))
  return result
 },[rows,search,status,order])
 const selected=selectedKey===undefined?localKey:selectedKey
 const chosen=visible.find(row=>row.key===selected)||visible[0]||null
 useEffect(()=>{setDetailOpen(false);setLocalKey(null)},[pageLabel])
 // Keep the visible inspector and author-edited form bound to exactly one row.
 // Filtering or paging can replace the first visible row without a click.
 useEffect(()=>{
  const key=chosen?.key||null
  if(key!==notified.current){
   notified.current=key
   if(key)onSelectionChange?.(key)
  }
 },[chosen?.key,onSelectionChange])
 function select(key:string){
  notified.current=key
  setLocalKey(key);onSelectionChange?.(key);setDetailOpen(true)
 }
 function onKeys(e:KeyboardEvent<HTMLElement>){
  if(e.target instanceof HTMLElement&&!e.target.closest('.review-queue-list'))return
  if(e.key==='Escape'){setDetailOpen(false);return}
  if(e.key!=='ArrowDown'&&e.key!=='ArrowUp'&&e.key.toLowerCase()!=='j'&&e.key.toLowerCase()!=='k')return
  if(!visible.length)return
  e.preventDefault()
  const i=visible.findIndex(row=>row.key===chosen?.key)
  const delta=e.key==='ArrowDown'||e.key.toLowerCase()==='j'?1:-1
  const nextIndex=Math.max(0,Math.min(visible.length-1,i+delta))
  select(visible[nextIndex].key)
  e.currentTarget.querySelectorAll<HTMLButtonElement>('.review-queue-row')[nextIndex]?.focus()
 }
 return <section className={'review-queue'+(comfortable?' review-queue-comfortable':'')} aria-label={title} onKeyDown={onKeys}>
  <div className="review-queue-head">
   <div><h3>{title}</h3><p>{description}</p></div>
   <span className="review-queue-count">{visible.length} / {rows.length} rows{pageLabel?' · '+pageLabel:''}</span>
  </div>
  <div className="review-queue-toolbar">
   <label className="review-queue-search"><span>Find in loaded rows</span>
    <input type="search" value={search} onChange={e=>setSearch(e.target.value)}
     placeholder="Filter title, quote or character…" aria-label="Filter loaded queue rows"/>
   </label>
   {options.length>0&&<label className="review-queue-filter"><span>Status</span>
    <select value={status} onChange={e=>setStatus(e.target.value)}>
     <option value="all">All statuses</option>
     {options.map(option=><option key={option} value={option}>{option.replaceAll('_',' ')}</option>)}
    </select>
   </label>}
   <label className="review-queue-sort"><span>Order</span>
    <select value={order} onChange={e=>setOrder(e.target.value as 'source'|'title'|'status')}>
     <option value="source">Source order</option>
     <option value="title">Title A–Z</option>
     <option value="status">Status</option>
    </select>
   </label>
   <div className="review-queue-density" role="group" aria-label="List density">
    <button aria-pressed={!comfortable} onClick={()=>setComfortable(false)} type="button">Compact</button>
    <button aria-pressed={comfortable} onClick={()=>setComfortable(true)} type="button">Comfortable</button>
   </div>
   {toolbar}
  </div>
  <div className={'review-queue-body'+(detailOpen?' review-queue-detail-open':'')}>
   <div className="review-queue-list" role="region" aria-label={title+' items'}>
    {loading&&<p className="review-queue-empty" role="status">Loading queue…</p>}
    {!loading&&visible.map((row,index)=><button type="button" key={row.key}
     className="review-queue-row"
     aria-current={chosen?.key===row.key?'true':undefined}
     onClick={()=>select(row.key)}>
     <span className="review-queue-index">{String(index+1).padStart(2,'0')}</span>
     <span className="review-queue-main">
      <strong>{row.title}</strong><small>{row.subtitle}</small>
      <span className="review-queue-preview">{row.preview}</span>
     </span>
     <span className="review-queue-side">
      {row.status&&<span className="review-queue-status">{row.status.replaceAll('_',' ')}</span>}
      {row.meta&&<small>{row.meta}</small>}
     </span>
    </button>)}
    {!loading&&!visible.length&&<p className="review-queue-empty">
     {rows.length?'No rows match the current filter.':emptyText}
    </p>}
   </div>
   <aside className="review-queue-inspector" aria-label={title+' selected detail'}>
    {chosen?<><div className="review-queue-inspector-head">
     <span>REVIEW DETAILS</span>
     <button className="review-queue-close" type="button" onClick={()=>setDetailOpen(false)}>Close</button>
    </div>
    {detail(chosen)}</>:<div className="review-queue-empty">Select a row to inspect full context.</div>}
   </aside>
  </div>
  {footer&&<div className="review-queue-footer">{footer}</div>}
  <p className="review-queue-shortcuts">Tip: click a row to inspect it, or use ↑/↓ and J/K when focused on the queue.</p>
 </section>
}
