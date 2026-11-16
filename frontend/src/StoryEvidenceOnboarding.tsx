import {useEffect,useState} from 'react'
import './story-evidence-onboarding.css'

type Lead={subject_name:string;predicate:string;object_text:string;start_book:number;quote:string}
type Discovery={total:number;scanned_sources:number;skipped_large_sources:number;candidates:Lead[];caveat:string}
type StructureSummary={source_count:number;indexed_sources:number;verified_sections:number;toc_fragment_links:number;structural_only:boolean}
export default function StoryEvidenceOnboarding({seriesId,onDiscover,onReview}:{
 seriesId:string;onDiscover:()=>void;onReview:()=>void
}){
 const [data,setData]=useState<Discovery|null>(null)
 const [error,setError]=useState('')
 const [loading,setLoading]=useState(true)
 const [structure,setStructure]=useState<StructureSummary|null>(null)
 useEffect(()=>{
   const controller=new AbortController()
   setLoading(true);setError('');setData(null);setStructure(null)
   void fetch('http://127.0.0.1:8000/api/series/'+encodeURIComponent(seriesId)+'/structure-overview',
     {signal:controller.signal})
     .then(async response=>response.ok?response.json() as Promise<StructureSummary>:null)
     .then(summary=>{if(!controller.signal.aborted)setStructure(summary)})
     .catch(()=>{/* Source leads remain usable if indexing summary is unavailable. */})
   fetch('http://127.0.0.1:8000/api/series/'+encodeURIComponent(seriesId)+'/discover?limit=5',
     {signal:controller.signal})
     .then(async r=>{if(!r.ok)throw Error('Source discovery is unavailable ('+r.status+')');return r.json() as Promise<Discovery>})
     .then(value=>{if(!controller.signal.aborted)setData(value)})
     .catch(e=>{if(!controller.signal.aborted)setError(String(e))})
     .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
   return ()=>controller.abort()
 },[seriesId])
 return <aside className="story-evidence-onboarding" aria-label="How to populate story intelligence">
  <span className="story-evidence-eyebrow">SOURCE LIBRARY CONNECTED · REVIEW REQUIRED</span>
  <h3>Your books are here. Their story intelligence has not been approved yet.</h3>
  <p>Universe, character minds, plot threads and story history use verified, author-approved statements.
     Importing novels preserves their original text but does not automatically turn AI interpretations into canon.</p>
  {loading&&<p role="status">Checking source passages for reviewable leads…</p>}
  {error&&<p role="alert">{error}</p>}
  {data&&<>
   <div className="story-evidence-metrics">
    <span><strong>{data.scanned_sources}</strong> source snapshots scanned</span>
    <span><strong>{data.total}</strong> unapproved leads found</span>
    <span><strong>{data.skipped_large_sources}</strong> sources skipped</span>
    {structure&&<>
     <span><strong>{structure.indexed_sources}/{structure.source_count}</strong> original sources indexed</span>
     <span><strong>{structure.verified_sections.toLocaleString()}</strong> exact structural sections</span>
    </>}
   </div>
   {!!data.candidates.length&&<div className="story-evidence-preview">
    <h4>Examples from your books — not yet canon</h4>
    {data.candidates.slice(0,3).map((lead,index)=><article key={index}>
     <small>Book {lead.start_book} · Requires original-context review</small>
     <strong>{lead.subject_name} · {lead.predicate.replaceAll('_',' ')} · {lead.object_text}</strong>
     <blockquote>{lead.quote}</blockquote>
    </article>)}
   </div>}
   {!data.total&&<p>The literal-pattern scanner found no candidates. This does not mean your books have no characters or history; use source-specific extraction to examine additional passages.</p>}
  </>}
  <div className="story-evidence-actions">
   <button type="button" onClick={onDiscover}>Explore source discoveries</button>
   <button type="button" onClick={onReview}>Review or add canon evidence</button>
  </div>
  <small>Nothing is promoted into canon automatically. As you approve source citations, these views populate from that reviewed evidence.</small>
 </aside>
}