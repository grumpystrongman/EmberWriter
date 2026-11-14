import {useEffect,useState} from 'react'

type Book={ordinal:number;filename:string;status:string;matched_sections:number;reason:string}
type Preview={books_in_archive:number;matched_books:number;unmatched_books:number;
 recoverable_sections:number;can_confirm:boolean;books:Book[];message:string}
const BASE='http://127.0.0.1:8000/api/series'

export default function SeriesEpubCollectionRecovery({seriesId,onIndexed}:{
 seriesId:string;onIndexed:()=>void
}){
 const [archive,setArchive]=useState<File|null>(null)
 const [preview,setPreview]=useState<Preview|null>(null)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState('')
 const [saved,setSaved]=useState('')
 useEffect(()=>{setArchive(null);setPreview(null);setError('');setSaved('')},[seriesId])
 async function send(confirm:boolean){
  if(!archive||busy)return
  setBusy(true);setError('');setSaved('')
  try{
   const body=new FormData();body.set('file',archive)
   const path=confirm?'epub-structure-zip-confirm':'epub-structure-zip-preview'
   const response=await fetch(`${BASE}/${encodeURIComponent(seriesId)}/${path}`,{method:'POST',body})
   const data=await response.json()
   if(!response.ok)throw Error(data.detail||'EPUB collection could not be verified')
   if(confirm){
    setSaved('Saved '+data.indexed_books+' book indexes and '+data.indexed_sections+' verified spine sections. No manuscripts or canon assertions were changed.')
    setPreview(null)
    onIndexed()
   }else setPreview(data as Preview)
  }catch(cause){setError(String(cause))}
  finally{setBusy(false)}
 }
 return <details className="source-collection-recovery">
  <summary>Recover chapter indexes for a series ZIP (multiple books)</summary>
  <p>Select the original numbered EPUB collection ZIP (up to 150 EPUBs, 60 MB).
   A preview checks the filename, book number, and every exact snapshot before anything is saved.
   Any unmatched book blocks the entire confirmation; no partial indexing occurs.</p>
  <label>Original EPUB collection ZIP
   <input type="file" accept=".zip,application/zip" onChange={e=>{
    setArchive(e.target.files?.[0]||null);setPreview(null);setSaved('');setError('')
   }}/>
  </label>
  <button type="button" disabled={!archive||busy} onClick={()=>void send(false)}>
   {busy?'Checking exact snapshot matches…':'Preview collection without changes'}
  </button>
  {error&&<p role="alert">{error}</p>}
  {saved&&<p role="status">{saved}</p>}
  {preview&&<div className="collection-recovery-results" role="status">
   <strong>{preview.matched_books} of {preview.books_in_archive} books match · {preview.recoverable_sections} structural sections</strong>
   <p>{preview.message}</p>
   <div className="collection-recovery-books">
    {preview.books.map(book=><div key={book.ordinal}>
     <strong>Book {book.ordinal} · {book.filename}</strong>
     <small>{book.status.replaceAll('_',' ')} · {book.matched_sections} sections · {book.reason}</small>
    </div>)}
   </div>
   <button type="button" disabled={!preview.can_confirm||busy} onClick={()=>void send(true)}>
    Save all {preview.matched_books} verified chapter indexes
   </button>
   <small>Confirming stores verified structural coordinates only. No EPUB bytes, canon approvals, inferred story chronology, or manuscript replacements.</small>
  </div>}
 </details>
}
