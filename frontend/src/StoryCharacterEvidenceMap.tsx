import {useEffect,useMemo,useState} from 'react'
import './story-character-evidence-map.css'

type Character={id:string;name:string;kind:string}
type Sample={source_id:string;source_hash:string;mention_start:number;mention_end:number;
 excerpt_start:number;excerpt_end:number;excerpt:string;mention:string;
 section_title:string|null;verified_original_epub:boolean}
type Book={book:number;volume:string;mention_count:number;source_count_with_mention:number;samples:Sample[]}
type Atlas={entity_name:string;books_examined:number;books_with_mentions:number;
 total_literal_mentions:number;books:Book[];nearby_character_names:{name:string;nearby_mention_count:number}[];
 limitations:string}
const BASE='http://127.0.0.1:8000/api/series'

export default function StoryCharacterEvidenceMap({seriesId,entities,onInspectSource}:{
 seriesId:string;entities:Character[];onInspectSource:(sourceId:string)=>void
}){
 const characters=useMemo(()=>entities.filter(e=>e.kind==='character'),[entities])
 const [selected,setSelected]=useState<string>('')
 const chosen=characters.some(x=>x.id===selected)?selected:characters[0]?.id||''
 const [atlas,setAtlas]=useState<Atlas|null>(null)
 const [loading,setLoading]=useState(false)
 const [error,setError]=useState('')
 const [expanded,setExpanded]=useState<number|null>(null)
 const [onlyPresent,setOnlyPresent]=useState(true)
 useEffect(()=>{
  const controller=new AbortController()
  setAtlas(null);setError('');setExpanded(null)
  if(!chosen)return
  setLoading(true)
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/character-presence?entity_id=${encodeURIComponent(chosen)}`,
   {signal:controller.signal})
   .then(async r=>{if(!r.ok)throw Error('Character source coverage unavailable');return r.json() as Promise<Atlas>})
   .then(data=>{if(!controller.signal.aborted)setAtlas(data)})
   .catch(err=>{if(!controller.signal.aborted)setError(String(err))})
   .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
  return()=>controller.abort()
 },[seriesId,chosen])
 const books=(atlas?.books||[]).filter(x=>!onlyPresent||x.mention_count)
 const maxCount=Math.max(1,...(atlas?.books||[]).map(b=>b.mention_count))
 return <section className="story-character-evidence-map" aria-label="Character appearances across sources">
  <header>
   <span>ACTUAL SOURCE MENTIONS / CROSS-BOOK MAP</span>
   <h3>Where the books mention your characters</h3>
   <p>Track exact name or alias appearances across the source library, with original EPUB positions and nearby quotations. A mention is not proof of a character appearing in a scene.</p>
  </header>
  <div className="character-map-controls">
   <label>Track character
    <select value={chosen} onChange={e=>setSelected(e.target.value)}>
     {characters.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
    </select>
   </label>
   <label className="character-map-check"><input type="checkbox" checked={onlyPresent} onChange={e=>setOnlyPresent(e.target.checked)}/> Only books with mentions</label>
  </div>
  {!characters.length&&<p>Define a character and an alias, if applicable, in the Canon Graph to begin tracking literal references.</p>}
  {loading&&<p role="status">Reading exact source positions across the series…</p>}
  {error&&<p role="alert">{error}</p>}
  {atlas&&<>
   <div className="character-map-metrics">
    <span><strong>{atlas.total_literal_mentions.toLocaleString()}</strong> literal mentions</span>
    <span><strong>{atlas.books_with_mentions}/{atlas.books_examined}</strong> books with matches</span>
    <span><strong>{atlas.nearby_character_names.length}</strong> other characters mentioned nearby</span>
   </div>
   {!!atlas.nearby_character_names.length&&<p className="character-map-caveat">Nearby textual names (not confirmed relationships): {atlas.nearby_character_names.map(x=>x.name+' ('+x.nearby_mention_count+')').join(', ')}</p>}
   <div className="character-map-books">
    {books.map(book=><article key={book.book}>
     <button className="character-map-book" aria-expanded={expanded===book.book}
      onClick={()=>setExpanded(current=>current===book.book?null:book.book)}>
      <span>Book {book.book} <small>{book.volume}</small></span>
      <span className="character-map-track"><i style={{width:`${Math.max(book.mention_count?2:0,book.mention_count/maxCount*100)}%`}}/></span>
      <strong>{book.mention_count.toLocaleString()} mentions</strong>
     </button>
     {expanded===book.book&&<div className="character-map-samples">
      {book.samples.map(item=><div key={item.source_id+':'+item.mention_start}>
       <small>{item.section_title||'Original source'} · character {item.mention_start.toLocaleString()} · {item.verified_original_epub?'Verified EPUB location':'Source snapshot only'}</small>
       <blockquote>{item.excerpt}</blockquote>
       <button type="button" onClick={()=>onInspectSource(item.source_id)}>Open original source</button>
      </div>)}
      {!book.samples.length&&<p>No cited name match in this book.</p>}
     </div>}
    </article>)}
   </div>
   <p className="character-map-caveat">{atlas.limitations} The map creates no canon assertions and does not establish motives, secrets, psychology or character knowledge.</p>
  </>}
 </section>
}
