import { useEffect, useMemo, useState } from 'react'
import './publishing-desk.css'

type StageId='readiness'|'interior'|'cover'|'audio'|'distribution'|'history'
type Stage={id:StageId;title:string;detail:string;status:'reviewed'|'needs_attention'|'not_started'|'optional';count:number}
type Issue={title?:string;detail?:string;message?:string;level:string;path?:string;code?:string;waived?:boolean}
type FileItem={filename:string;relative_path:string;suffix:string;bytes:number;role:string;sha256:string;modified_at:string}
type Receipt={id:string;created_at:string;fingerprint:string;note:string;chapter_count:number;editorial_blockers:number;editorial_warnings:number;distribution_valid:boolean;current:boolean}
type Dashboard={project_name:string;chapter_count:number;words:number;source_fingerprint:string;compile_error:string|null;
  formats:Record<'epub'|'pdf'|'docx',boolean>;chapters:{id:string;title:string;path:string;words:number}[];
  files:FileItem[];editorial:{blockers:number;warnings:number;waived:number;issues:Issue[];disclaimer:string};
  distribution:{valid:boolean;issues:Issue[];enabled_editions:number;retailers:string[]};
  profile:{title:string;author:string;description:string;publisher:string;language:string;editions:{id:string;format:string;enabled:boolean;retailers:string[];interior_path:string;cover_path:string}[]};
  stages:Stage[];receipts:Receipt[];reviewed_current:boolean;privacy:string;limitations:string}
type Props={apiBase:string;slug:string;disabled:boolean;onGo:(stage:StageId)=>void;onOpenSource?:(path:string)=>void}
const ICONS:Record<StageId,string>={readiness:'◈',interior:'▤',cover:'▧',audio:'◉',distribution:'✦',history:'↺'}
const FORMAT_DETAILS={epub:'Reflowable eBook',docx:'Editorial manuscript',pdf:'Print layout'}
function bytes(n:number){return n>=1048576?(n/1048576).toFixed(1)+' MB':Math.max(1,Math.round(n/1024))+' KB'}
async function json<T>(url:string,init?:RequestInit):Promise<T>{
 const response=await fetch(url,{...init,headers:{'Content-Type':'application/json',...(init?.headers||{})}})
 const data=await response.json().catch(()=>({}))
 if(!response.ok)throw Error(data.detail||'Request failed: '+response.status)
 return data as T
}
export default function PublishingDesk({apiBase,slug,disabled,onGo,onOpenSource}:Props){
 const endpoint=`${apiBase}/projects/${encodeURIComponent(slug)}/publishing-desk`
 const [report,setReport]=useState<Dashboard|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [message,setMessage]=useState('')
 const [focused,setFocused]=useState<StageId>('readiness')
 const [inspectIssue,setInspectIssue]=useState<number|null>(null)
 const [reviewNote,setReviewNote]=useState('')
 const [ack,setAck]=useState(false)
 const [confirm,setConfirm]=useState(false)
 const [showAllFiles,setShowAllFiles]=useState(false)
 async function refresh(){
   setBusy(true);setError('');setMessage('')
   try{const next=await json<Dashboard>(endpoint);setReport(next);setConfirm(false);setAck(false)}
   catch(e){setError(String(e))}
   finally{setBusy(false)}
 }
 useEffect(()=>{
   let active=true
   setReport(null);setMessage('');setError('');setReviewNote('')
   void json<Dashboard>(endpoint).then(r=>{if(active)setReport(r)}).catch(e=>{if(active)setError(String(e))})
   return()=>{active=false}
 },[endpoint])
 const checkedStages=useMemo(()=>report?.stages.filter(s=>s.status==='reviewed').length||0,[report])
 const current=report?.stages.find(s=>s.id===focused)
 const relevantIssues=focused==='distribution'?report?.distribution.issues:report?.editorial.issues
 async function sign(){
   if(!report||busy||disabled)return
   setBusy(true);setError('')
   try{
     await json(endpoint+'/signoff',{method:'POST',body:JSON.stringify({
       fingerprint:report.source_fingerprint,note:reviewNote.trim(),acknowledged:ack,
     })})
     const next=await json<Dashboard>(endpoint)
     setReport(next);setMessage('Private author-review receipt created. No files were sent or published.')
     setReviewNote('');setAck(false);setConfirm(false)
   }catch(e){setError(String(e))}
   finally{setBusy(false)}
 }
 return <section className="pubdesk" aria-label="Private publishing command deck">
   <header className="pubdesk-hero">
     <div className="pubdesk-heading">
       <div><span className="pubdesk-kicker">THE AUTHOR'S PRIVATE PUBLISHING ATELIER · PART IV</span>
         <h2>Make the book ready for the world.</h2>
         <p>From your manuscript to polished editions, reviewable files, and a deliberate release. Every step stays under your control.</p></div>
       <div className="pubdesk-compass" aria-hidden="true"><span>✦</span><small>CREATE<br/>REVIEW<br/>RELEASE</small></div>
     </div>
     <div className="pubdesk-overview-strip">
       <div><span>COMPILED CHAPTERS</span><strong>{report?.chapter_count??'—'}</strong></div>
       <div><span>MANUSCRIPT WORDS</span><strong>{report?.words.toLocaleString()??'—'}</strong></div>
       <div><span>STAGES REVIEWED</span><strong>{checkedStages}<small> / 6</small></strong></div>
       <div><span>RELEASE REVIEW</span><strong className={report?.reviewed_current?'pubdesk-ready':'pubdesk-awaiting'}>
          {report?.reviewed_current?'Recorded':'Awaiting author'}</strong></div>
       <button type="button" onClick={()=>void refresh()} disabled={disabled||busy}>↻ Refresh checks</button>
     </div>
   </header>
   {error&&<p className="pubdesk-error" role="alert">{error}</p>}
   {message&&<p className="pubdesk-success" role="status">{message}</p>}
   {!report?<div className="pubdesk-loading" role="status">{error?'Publishing data could not be loaded.':'Reading project publishing state locally…'}</div>:<>
     <div className="pubdesk-section-caption"><span>YOUR RELEASE JOURNEY</span><small>Choose a milestone to inspect it</small></div>
     <nav className="pubdesk-journey" aria-label="Publishing milestones">
       {report.stages.map((stage,i)=><button type="button" key={stage.id} aria-pressed={focused===stage.id}
         onClick={()=>{setFocused(stage.id);setInspectIssue(null)}}>
         <span className="pubdesk-stage-count">{String(i+1).padStart(2,'0')}</span>
         <span className="pubdesk-stage-icon" aria-hidden="true">{ICONS[stage.id]}</span>
         <strong>{stage.title}</strong>
         <small>{stage.status==='reviewed'?'● Evidence ready':stage.status==='optional'?'◇ Optional':stage.status==='needs_attention'?'◆ Needs review':'○ Not started'}</small>
       </button>)}
     </nav>

     <div className="pubdesk-main">
       <section className="pubdesk-focus">
         <div className="pubdesk-focus-top"><span>SELECTED MILESTONE</span><small>{report.stages.findIndex(s=>s.id===focused)+1} OF 6</small></div>
         <div className="pubdesk-focus-title"><div className="pubdesk-focus-emblem" aria-hidden="true">{ICONS[focused]}</div>
           <div><h3>{current?.title}</h3><p>{current?.detail}</p></div></div>
         {focused==='readiness'&&<>
           <div className="pubdesk-review-metrics">
             <div><strong>{report.editorial.blockers}</strong><span>Structural blockers</span></div>
             <div><strong>{report.editorial.warnings}</strong><span>Open warnings</span></div>
             <div><strong>{report.editorial.waived}</strong><span>Authored waivers</span></div>
           </div>
           <p className="pubdesk-context">Editorial checks are advisory, not proof of publication readiness. You can inspect each issue and record author decisions in the complete readiness gate.</p>
         </>}
         {focused==='interior'&&<>
           <div className="pubdesk-formats">{(['epub','docx','pdf'] as const).map(format=><div key={format} className={report.formats[format]?'built':''}>
             <strong>{format.toUpperCase()}</strong><small>{FORMAT_DETAILS[format]}</small>
             <span>{report.formats[format]?'● Existing export':'○ Not yet generated'}</span>
           </div>)}</div>
           <p className="pubdesk-context">Compile follows Binder order and each document's Include in Compile setting. Inspect the contents in the preview before creating downloadable files.</p>
           {report.compile_error&&<p className="pubdesk-caution">{report.compile_error}</p>}
         </>}
         {focused==='cover'&&<>
           <div className="pubdesk-bookmock"><div aria-hidden="true" className="pubdesk-book-art"><span>✦</span><b>{report.profile.title}</b><small>{report.profile.author||'AUTHOR NOT SET'}</small></div>
             <div><strong>Cover and metadata</strong><p>{report.profile.author||'Set an author or pen name'} · {report.profile.language.toUpperCase()}</p><p>{report.files.filter(x=>x.role==='cover').length} cover assets identified in local exports</p>
               <small>This illustrated cover is a workspace placeholder, not a generated cover file.</small></div></div>
         </>}
         {focused==='audio'&&<>
           <div className="pubdesk-optional"><span aria-hidden="true">♫</span><div><strong>A new way to experience your story</strong>
             <p>Audiobook production remains optional. The existing narration studio offers local audio creation and preparation. No narration begins automatically.</p></div></div>
         </>}
         {focused==='distribution'&&<>
           <div className="pubdesk-review-metrics"><div><strong>{report.distribution.enabled_editions}</strong><span>Enabled editions</span></div>
             <div><strong>{report.distribution.retailers.length}</strong><span>Target retailers</span></div>
             <div><strong>{report.distribution.issues.filter(i=>i.level==='error').length}</strong><span>Validation errors</span></div></div>
           <div className="pubdesk-retailers">{report.distribution.retailers.map(retailer=><span key={retailer}>{retailer.replaceAll('_',' ')}</span>)}</div>
           <p className="pubdesk-context">Release validation uses local package and metadata checks. Nothing is uploaded or submitted until you deliberately use an external publisher outside this desk.</p>
         </>}
         {focused==='history'&&<>
           <div className="pubdesk-review-metrics"><div><strong>{report.receipts.length}</strong><span>Release review receipts</span></div>
             <div><strong>{report.files.length}</strong><span>Recent export artifacts</span></div>
             <div><strong>{report.reviewed_current?'Yes':'No'}</strong><span>Current manuscript reviewed</span></div></div>
           <p className="pubdesk-context">Compare and restore project checkpoints in the existing History workspace. Publishing receipts record author acknowledgment without modifying the manuscript.</p>
         </>}
         {(focused==='readiness'||focused==='distribution')&&<div className="pubdesk-issues">
           <div className="pubdesk-minor-head"><strong>ITEMS WORTH INSPECTING</strong><span>{relevantIssues?.length||0}</span></div>
           {(relevantIssues||[]).slice(0,7).map((issue,i)=><button type="button" key={i} aria-expanded={inspectIssue===i} onClick={()=>setInspectIssue(inspectIssue===i?null:i)}>
             <span className={'pubdesk-level '+issue.level}>{issue.waived?'WAIVED':issue.level.toUpperCase()}</span>
             <div><strong>{issue.title||issue.message||issue.code}</strong>
             {inspectIssue===i&&<p>{issue.detail||issue.message}{issue.path?' · Source: '+issue.path:''}</p>}</div><span aria-hidden="true">{inspectIssue===i?'−':'+'}</span>
           </button>)}
           {!relevantIssues?.length&&<div className="pubdesk-none">No issues reported in this category. This is not a retailer certification.</div>}
         </div>}
         <button type="button" className="pubdesk-action" disabled={disabled} onClick={()=>onGo(focused)}>
           Open {focused==='interior'?'preview & book files':focused==='distribution'?'submissions & release':current?.title.toLowerCase()} <span>↗</span></button>
       </section>
       <aside className="pubdesk-side">
         <div className="pubdesk-side-head"><span>MANUSCRIPT IN COMPILE ORDER</span><strong>{report.chapter_count} chapters</strong></div>
         <div className="pubdesk-chapters">{report.chapters.length?report.chapters.slice(0,24).map((chapter,i)=>
           <button type="button" key={chapter.id} disabled={!onOpenSource} onClick={()=>onOpenSource?.(chapter.path)}>
             <span>{String(i+1).padStart(2,'0')}</span><div><strong>{chapter.title}</strong><small>{chapter.words.toLocaleString()} words</small></div><span aria-hidden="true">↗</span>
           </button>):<p>No chapters selected for compilation. Check your Binder settings.</p>}</div>
         <div className="pubdesk-side-privacy"><span aria-hidden="true">♢</span><p>PRIVATE BY DESIGN<br/><small>Your manuscript stays on this computer. Nothing in this publishing desk automatically uploads or distributes it.</small></p></div>
       </aside>
     </div>

     <div className="pubdesk-section-caption"><span>YOUR FINISHED ASSETS</span><small>Existing local exports and their source fingerprints</small></div>
     <div className="pubdesk-assets">
       {!report.files.length?<div className="pubdesk-empty"><span>▧</span><strong>Your book files will appear here.</strong><p>Choose Book interiors, preview the manuscript and compile one or more formats when ready.</p>
         <button type="button" onClick={()=>onGo('interior')}>Go to book files ↗</button></div>:
       report.files.slice(0,showAllFiles?80:6).map(file=><article key={file.relative_path}>
         <div className="pubdesk-asset-symbol">{file.suffix.toUpperCase().slice(1)}</div>
         <div><strong>{file.filename}</strong><small>{file.role.replaceAll('_',' ')} · {bytes(file.bytes)} · SHA-256 {file.sha256.slice(0,12)}…</small></div>
         <a href={`${apiBase}/projects/${encodeURIComponent(slug)}/exports/download?path=${encodeURIComponent(file.relative_path)}`} download={file.filename}>Download ↗</a>
       </article>)}
       {report.files.length>6&&<button type="button" className="pubdesk-show" onClick={()=>setShowAllFiles(v=>!v)}>{showAllFiles?'Show fewer assets':'See all '+report.files.length+' artifacts'}</button>}
     </div>

     <section className="pubdesk-signoff">
       <div><span>AUTHOR-CONTROLLED RELEASE RECORD</span><h3>The last decision is yours.</h3>
         <p>You can record that you reviewed the current manuscript and release settings. This is a local audit receipt, not an approval from a retailer and not permission to publish anything automatically.</p>
         <label>What did you review, and what remains to check?
           <textarea value={reviewNote} maxLength={1200} disabled={disabled||busy}
             onChange={e=>{setReviewNote(e.target.value);setConfirm(false)}}
             placeholder="I checked the manuscript ordering, reviewed the preview, and noted which release warnings remain…"/></label>
         <label className="pubdesk-ack"><input type="checkbox" checked={ack} disabled={disabled||busy}
           onChange={e=>{setAck(e.target.checked);setConfirm(false)}}/>
           I understand this records my review only and does not mean the book is approved for publication.</label>
         {confirm?<div className="pubdesk-confirm" role="group" aria-label="Confirm private review receipt">
           <strong>Record this author review?</strong><p>{report.editorial.blockers} editorial blockers and {report.distribution.issues.filter(i=>i.level==='error').length} distribution errors are currently reported. These will be preserved in your receipt.</p>
           <div><button type="button" disabled={disabled||busy} onClick={()=>void sign()}>Confirm and record locally</button>
             <button type="button" onClick={()=>setConfirm(false)}>Cancel</button></div>
         </div>:<button type="button" className="pubdesk-action" disabled={disabled||busy||!ack||reviewNote.trim().length<12} onClick={()=>setConfirm(true)}>
           Record private release review ↗</button>}
       </div>
       <aside><strong>REVIEW HISTORY</strong>
         {report.receipts.length?report.receipts.slice(0,5).map(r=><article key={r.id}>
           <span>{r.current?'● Current manuscript':'○ Earlier manuscript / settings'}</span><strong>{new Date(r.created_at).toLocaleString()}</strong>
           <p>{r.note}</p><small>{r.editorial_blockers} editorial blockers · {r.editorial_warnings} warnings</small></article>):<p>No release reviews recorded yet. Your acknowledgment will be saved privately with the current manuscript fingerprint.</p>}
       </aside>
     </section>
     <footer className="pubdesk-disclaimer">{report.limitations}</footer>
   </>}
 </section>
}
