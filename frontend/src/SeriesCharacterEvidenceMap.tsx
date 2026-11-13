import {useEffect,useMemo,useState} from 'react'
import './series-character-map.css'
type Character={id:string;name:string;kind:string}
type Volume={book:number;title:string;matching_windows:number}
type MapReport={series_id:string;entity_id:string;name:string;query:string;max_book:number;
 total_windows:number;first_attested_book:number|null;books:Volume[];disclaimer:string}
type Props={seriesId:string;characters:Character[];maxBook:number;
 onExploreBook:(book:number,name:string)=>void}
export default function SeriesCharacterEvidenceMap({seriesId,characters,maxBook,onExploreBook}:Props){
 const [selected,setSelected]=useState('')
 const [report,setReport]=useState<MapReport|null>(null)
 const [error,setError]=useState('')
 const [loading,setLoading]=useState(false)
 const [activeBook,setActiveBook]=useState<number|null>(null)
 useEffect(()=>{setSelected('');setReport(null);setActiveBook(null)},[seriesId])
 useEffect(()=>{
   if(characters.length&&!characters.some(person=>person.id===selected)){
     setSelected(characters[0].id)
   }
 },[characters,selected])
 useEffect(()=>{
   if(!selected||!seriesId)return
   const controller=new AbortController()
   setLoading(true);setError('');setReport(null);setActiveBook(null)
   const qs=new URLSearchParams({max_book:String(maxBook)})
   const url='http://127.0.0.1:8000/api/series/'+encodeURIComponent(seriesId)+'/characters/'+encodeURIComponent(selected)+'/evidence-map?'+qs
   void fetch(url,{signal:controller.signal})
     .then(async response=>{const data=await response.json();if(!response.ok)throw Error(data.detail||'Unable to map series evidence');return data as MapReport})
     .then(data=>{if(!controller.signal.aborted)setReport(data)})
     .catch(cause=>{if(!controller.signal.aborted)setError(String(cause))})
     .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
   return()=>controller.abort()
 },[seriesId,selected,maxBook])
 const maxHits=useMemo(()=>Math.max(1,...(report?.books||[]).map(v=>v.matching_windows)),[report])
 const current=report?.books.find(v=>v.book===activeBook)
 if(!characters.length)return null
 return <section className="character-evidence-map" aria-label="Character evidence across books">
   <div className="cem-heading"><div><small>THE CHARACTER EVIDENCE ATLAS / LOCAL SOURCE RESEARCH</small>
     <h3>Follow a character across the shelves.</h3>
     <p>Choose a character and a book to inspect exactly where their name is mentioned. This shows sources—not personality, story events or approved canon.</p>
   </div><span className="cem-scope">{report?.books.length||maxBook} BOOKS IN SCOPE</span></div>
   <div className="cem-characters" role="group" aria-label="Select a series character">
     {characters.map(person=><button key={person.id} type="button" aria-pressed={selected===person.id}
       onClick={()=>setSelected(person.id)}>{person.name}</button>)}
   </div>
   {loading&&<p className="cem-status" role="status">Counting private source passages…</p>}
   {error&&<p className="cem-error" role="alert">{error}</p>}
   {report&&!loading&&<>
     <div className="cem-summary"><div><strong>{report.total_windows.toLocaleString()}</strong><span>matching text windows</span></div>
       <div><strong>{report.books.filter(v=>v.matching_windows>0).length}</strong><span>books with source mentions</span></div>
       <div><strong>{report.first_attested_book===null?'—':String(report.first_attested_book).padStart(2,'0')}</strong><span>first literal mention</span></div>
     </div>
     <div className="cem-chart-scroll" role="group" aria-label={'Evidence density for '+report.name+' through book '+maxBook}>
       <div className="cem-chart">
         {report.books.map(volume=>{
           const chosen=activeBook===volume.book
           return <button key={volume.book} type="button" className={chosen?'active':''}
             aria-pressed={chosen}
             aria-label={'Book '+volume.book+': '+volume.title+', '+volume.matching_windows+' matching source windows'}
             title={'Book '+volume.book+' · '+volume.title+' · '+volume.matching_windows+' windows'}
             onClick={()=>setActiveBook(chosen?null:volume.book)}>
             <span className="cem-bar-rail"><span className="cem-bar"
               style={{height:(volume.matching_windows?Math.max(5,Math.round(volume.matching_windows/maxHits*100)):0)+'%'}}/></span>
             <small>{volume.book%10===0||volume.book===1?volume.book:''}</small>
           </button>
         })}
       </div>
     </div>
     {current&&<div className="cem-book-focus">
       <div><small>BOOK {String(current.book).padStart(2,'0')}</small>
         <strong>{current.title}</strong>
         <span>{current.matching_windows.toLocaleString()} matching text windows</span>
       </div>
       <button type="button" disabled={current.matching_windows===0}
         onClick={()=>onExploreBook(current.book,report.query)}>Inspect cited passages ↗</button>
     </div>}
     <p className="cem-caveat">{report.disclaimer}</p>
   </>}
 </section>
}
