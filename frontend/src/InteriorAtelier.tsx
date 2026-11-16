import { useEffect, useState } from 'react'
import './interior-atelier.css'

type Format='epub'|'docx'|'pdf'
type Preset='ebook'|'manuscript'|'paperback'|'bundle'
type Reader='phone'|'tablet'|'ereader'|'print'
type PreviewDocument={title:string;path:string;html:string;word_count:number}
type Preview={title:string;author:string;documents:PreviewDocument[];words:number}
type Output={export_id:string;title:string;documents:number;words:number;
  artifacts:{format:Format;filename:string;relative_path:string;bytes:number}[]}
const presets:{id:Preset;name:string;category:string;symbol:string;description:string;formats:Format[]}[]=[
  {id:'ebook',name:'Digital edition',category:'EBOOK',symbol:'▤',
    description:'A reflowable EPUB with a navigable chapter table of contents.',formats:['epub']},
  {id:'manuscript',name:'Editorial manuscript',category:'SUBMISSION',symbol:'✎',
    description:'An editable DOCX for editorial review or submissions.',formats:['docx']},
  {id:'paperback',name:'Print interior',category:'PAPERBACK',symbol:'▥',
    description:'A PDF laid out at the selected trim size for print review.',formats:['pdf']},
  {id:'bundle',name:'Complete set',category:'ALL EDITIONS',symbol:'✦',
    description:'Generate EPUB, DOCX and PDF together in one local operation.',formats:['epub','docx','pdf']},
]
const readers:{id:Reader;label:string;description:string}[]=[
  {id:'phone',label:'Phone',description:'Compact reflow'},
  {id:'ereader',label:'eReader',description:'Reading width'},
  {id:'tablet',label:'Tablet',description:'Wide reflow'},
  {id:'print',label:'Print',description:'Page simulation'},
]
const safeHtml=(source:string)=>'<!doctype html><html><head><meta charset="utf-8"/>'+ 
'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data: blob:"><style>'+
'body{margin:0;padding:24px 25px;font:16px/1.72 Georgia,serif;color:#26212c;background:#faf7ed;overflow-wrap:anywhere}'+
'p{margin:0 0 1em}h1,h2,h3{text-align:center;line-height:1.28}blockquote{border-left:2px solid #c0a38c;margin:1em 0;padding-left:1em}'+
'a{color:#6b476b}img{max-width:100%}table{max-width:100%;overflow:auto}'+
'</style></head><body>'+source+'</body></html>'
async function request<T>(url:string,body?:unknown):Promise<T>{
 const res=await fetch(url,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},
  ...(body===undefined?{}:{body:JSON.stringify(body)})})
 const data=await res.json().catch(()=>({}))
 if(!res.ok)throw Error(data.detail||'Request failed: '+res.status)
 return data as T
}
export default function InteriorAtelier({apiBase,slug,title:defaultTitle,author:defaultAuthor,disabled,onBuilt}:{
 apiBase:string;slug:string;title:string;author:string;disabled:boolean;onBuilt:()=>Promise<void>
}){
 const [preset,setPreset]=useState<Preset>('ebook')
 const [reader,setReader]=useState<Reader>('ereader')
 const [preview,setPreview]=useState<Preview|null>(null)
 const [index,setIndex]=useState(0)
 const [title,setTitle]=useState(defaultTitle)
 const [author,setAuthor]=useState(defaultAuthor)
 const [trim,setTrim]=useState<'6x9'|'5x8'|'5.5x8.5'>('6x9')
 const [building,setBuilding]=useState(false)
 const [loading,setLoading]=useState(false)
 const [error,setError]=useState('')
 const [message,setMessage]=useState('')
 const [output,setOutput]=useState<Output|null>(null)
 const [showSettings,setShowSettings]=useState(false)
 const [confirm,setConfirm]=useState(false)
 const current=presets.find(p=>p.id===preset)!
 const chapter=preview?.documents[index]||null
 const sizes={'6x9':[6,9],'5x8':[5,8],'5.5x8.5':[5.5,8.5]}
 useEffect(()=>{setTitle(defaultTitle);setAuthor(defaultAuthor);setPreview(null);setOutput(null);setError('');setConfirm(false)},[slug,defaultTitle,defaultAuthor])
 async function loadPreview(){
   if(loading||disabled)return
   setLoading(true);setError('')
   try{
     const result=await request<Preview>(`${apiBase}/projects/${encodeURIComponent(slug)}/preview`,{
       title:title.trim(),author:author.trim(),trim_width:sizes[trim][0],trim_height:sizes[trim][1],
     })
     setPreview(result);setIndex(0);setMessage('Private preview updated from the current Binder selection.')
   }catch(e){setError(String(e))}
   finally{setLoading(false)}
 }
 async function build(){
   if(building||disabled||!confirm)return
   setBuilding(true);setError('');setMessage('');setConfirm(false)
   try{
     const result=await request<Output>(`${apiBase}/projects/${encodeURIComponent(slug)}/publish`,{
       title:title.trim(),author:author.trim(),language:'en',
       formats:current.formats,include_toc:true,trim_width:sizes[trim][0],trim_height:sizes[trim][1],
     })
     setOutput(result)
     await onBuilt()
     setMessage('New book files were compiled locally. Download each asset to inspect it before submitting anywhere.')
   }catch(e){setError(String(e))}
   finally{setBuilding(false)}
 }
 return <section className="interioratelier" aria-label="Interactive book interior workshop">
   <div className="interioratelier-head"><span>PRIVATE BOOK INTERIOR STUDIO</span><h4>Shape your next edition.</h4>
     <p>Choose how readers will encounter your book. Preview actual chapter content, then generate the formats you select—never automatically.</p></div>
   <div className="interioratelier-presets" role="group" aria-label="Choose a compile preset">{presets.map(item=>
     <button key={item.id} type="button" aria-pressed={preset===item.id} onClick={()=>{setPreset(item.id);setConfirm(false);setOutput(null)}}>
       <span>{item.category}</span><div className="interioratelier-presets-icon">{item.symbol}</div>
       <strong>{item.name}</strong><small>{item.description}</small></button>)}</div>
   <div className="interioratelier-content">
     <div className="interioratelier-reader">
       <div className="interioratelier-device-controls"><div><strong>READER PREVIEW</strong><small>Actual manuscript, not a generated mockup</small></div>
         <div className="interioratelier-device-switch" role="group" aria-label="Reader simulation">
           {readers.map(device=><button key={device.id} type="button" aria-pressed={reader===device.id}
             title={device.description} onClick={()=>setReader(device.id)}>{device.label}</button>)}</div>
       </div>
       <div className="interioratelier-paper-backdrop">
         <div className={'interioratelier-device '+reader}>
           <div className="interioratelier-device-top"><span>{reader==='phone'?'● 9:41':reader==='ereader'?'✦ eReader':reader==='tablet'?'Tablet':'Print preview'}</span>
             <span>{reader==='phone'?'●●●':'EmberWriter'}</span></div>
           {chapter?<div className="interioratelier-paper"><h5>{chapter.title}</h5>
             <iframe title={'Private preview of '+chapter.title} sandbox="" srcDoc={safeHtml(chapter.html)}/></div>:
             <div className="interioratelier-paper interioratelier-preview-empty"><span>❧</span><strong>Your words belong here.</strong>
               <p>Build a private reading preview to see your existing manuscript on the page.</p></div>}
           <div className="interioratelier-device-bottom"><span>{preview?'Chapter '+(index+1)+' / '+preview.documents.length:'Preview pending'}</span><span>◆</span></div>
         </div>
       </div>
       {preview&&<div className="interioratelier-chapter-navigation">
         <button type="button" disabled={index===0} onClick={()=>setIndex(i=>Math.max(i-1,0))}>← Previous</button>
         <label>Chapter<select value={index} onChange={e=>setIndex(Number(e.target.value))}>
           {preview.documents.map((ch,i)=><option key={ch.path} value={i}>{i+1}. {ch.title}</option>)}</select></label>
         <button type="button" disabled={index>=preview.documents.length-1} onClick={()=>setIndex(i=>i+1)}>Next →</button>
       </div>}
       <button className="interioratelier-preview-button" type="button" disabled={disabled||loading||!title.trim()} onClick={()=>void loadPreview()}>
         {loading?'Loading manuscript…':'↻ Build / refresh private preview'}</button>
     </div>
     <aside className="interioratelier-inspector">
       <span>EDITION DETAILS</span><h5>{current.name}</h5><p>{current.description}</p>
       <div className="interioratelier-output"><strong>WILL CREATE</strong><div>{current.formats.map(format=><span key={format}>{format.toUpperCase()}</span>)}</div></div>
       <button type="button" className="interioratelier-settings-toggle" aria-expanded={showSettings}
         onClick={()=>setShowSettings(value=>!value)}>{showSettings?'▾ Hide':'▸ Edit'} book details & trim size</button>
       {showSettings&&<div className="interioratelier-fields">
         <label>Book title<input maxLength={240} value={title} onChange={e=>setTitle(e.target.value)}/></label>
         <label>Author / pen name<input maxLength={240} value={author} onChange={e=>setAuthor(e.target.value)}/></label>
         <label>Trim size<select value={trim} onChange={e=>setTrim(e.target.value as typeof trim)}>
           <option value="6x9">6 × 9 inches</option><option value="5x8">5 × 8 inches</option>
           <option value="5.5x8.5">5.5 × 8.5 inches</option></select></label>
       </div>}
       <div className="interioratelier-safety"><strong>Before you compile</strong><p>Chapter order comes from your Binder. The original manuscript is not altered. EPUB uses reflowable layout; print settings apply to PDF.</p></div>
       {!confirm?<button className="interioratelier-build" type="button" disabled={disabled||building||!title.trim()}
         onClick={()=>setConfirm(true)}>Prepare {current.name.toLowerCase()} files <span>↗</span></button>:
         <div className="interioratelier-confirm" role="group" aria-label="Confirm creation of local book editions">
           <strong>Create {current.formats.map(f=>f.toUpperCase()).join(', ')}?</strong>
           <p>Files will be generated in your project's local exports folder. No files will be uploaded to a publisher.</p>
           <button type="button" disabled={disabled||building} onClick={()=>void build()}>{building?'Compiling…':'Confirm local build'}</button>
           <button type="button" onClick={()=>setConfirm(false)}>Cancel</button>
         </div>}
       {error&&<p className="interioratelier-error" role="alert">{error}</p>}
       {message&&<p className="interioratelier-message" role="status">{message}</p>}
       {output&&<div className="interioratelier-outputs"><strong>{output.artifacts.length} format(s) ready</strong>
         {output.artifacts.map(file=><a key={file.relative_path}
           href={`${apiBase}/projects/${encodeURIComponent(slug)}/exports/download?path=${encodeURIComponent(file.relative_path)}`}
           download={file.filename}>{file.format.toUpperCase()} · {file.filename} ↗</a>)}</div>}
     </aside>
   </div>
   <footer>Preview simulations use your actual compiled chapter HTML. Always inspect EPUB on real reading apps and review print proofs before publication.</footer>
 </section>
}
