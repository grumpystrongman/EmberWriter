import { useEffect, useRef, useState } from 'react'
import { HELP_ARTICLES, searchHelp, type HelpArticle } from './author-help'
import type { Workspace } from './workspace-types'
import './ember-guides.css'

type Props = {
  workspace:Workspace;initialQuery:string;onNavigate:(next:Workspace)=>void;onExit:()=>void
}
export default function EmberGuides({workspace,initialQuery,onNavigate,onExit}:Props){
 const [query,setQuery]=useState(initialQuery)
 const [selected,setSelected]=useState<HelpArticle|null>(null)
 const [stepIndex,setStepIndex]=useState(0)
 const [found,setFound]=useState('')
 const [confirmed,setConfirmed]=useState<string[]>([])
 const highlighted=useRef<HTMLElement|null>(null)
 useEffect(()=>{setQuery(initialQuery)},[initialQuery])
 useEffect(()=>()=>{highlighted.current?.classList.remove('ember-guide-target')},[])
 const matches=searchHelp(query)
 const step=selected?.steps[stepIndex]
 function choose(article:HelpArticle){
   highlighted.current?.classList.remove('ember-guide-target')
   highlighted.current=null
   setSelected(article);setStepIndex(0);setConfirmed([]);setFound('')
 }
 function jump(index:number){
   highlighted.current?.classList.remove('ember-guide-target')
   highlighted.current=null
   setStepIndex(index);setFound('')
 }
 function locate(){
   highlighted.current?.classList.remove('ember-guide-target')
   highlighted.current=null
   if(!step)return
   if(workspace!==step.workspace){
     setFound('This step is in '+step.workspace+'. Use Open workspace first.')
     return
   }
   let target:HTMLElement|null=null
   try{target=Array.from(document.querySelectorAll<HTMLElement>(step.target))
     .find(element=>element.getBoundingClientRect().width>0
       &&element.getBoundingClientRect().height>0)||null}catch{target=null}
   if(!target){
     setFound('The documented control is not visible in this version or screen state. Use the manual fallback below.')
     return
   }
   highlighted.current=target
   target.classList.add('ember-guide-target')
   target.scrollIntoView({block:'center',inline:'nearest',behavior:'auto'})
   if(target.matches('button,a,input,select,textarea,[tabindex]'))target.focus({preventScroll:true})
   setFound('Control located and highlighted. No action was taken for you.')
 }
 return <section className="ember-guides" aria-label="Offline How-To library">
   <div className="ember-guide-head"><div><strong>How-To & guided help</strong>
     <small>Offline instructions · pre-release edition</small></div>
     <button type="button" onClick={onExit} aria-label="Close How-To guides">Close</button></div>
   {!selected?<div className="ember-guide-library">
     <label htmlFor="ember-guide-search">Search the guides
       <input id="ember-guide-search" type="search" value={query} onChange={e=>setQuery(e.target.value)}
         placeholder="EPUB, undo, character, scene, backup…"/>
     </label>
     <div className="ember-guide-count" role="status">{matches.length} guide{matches.length===1?'':'s'} found</div>
     {matches.map(article=><button type="button" key={article.id} onClick={()=>choose(article)}
       className="ember-guide-card">
       <span>{article.category}</span><strong>{article.title}</strong>
       <small>{article.summary}</small><span className="ember-guide-card-action">Start walkthrough ↗</span>
     </button>)}
     {!matches.length&&<p>No verified steps match this search. Try "EPUB", "restore", "series", "scene" or "backup".</p>}
     <p className="ember-guide-disclaimer">These are preview-version walkthroughs, not yet a complete certified stable-release wiki. They do not require a model or access to your manuscript.</p>
   </div>:<div className="ember-guide-walkthrough">
     <button className="ember-guide-back-library" type="button" onClick={()=>{setSelected(null);setFound('')}}>← All guides</button>
     <span className="ember-guide-category">{selected.category} · {selected.release} preview</span>
     <h3>{selected.title}</h3><p>{selected.summary}</p>
     {selected.screenshots[0]&&<img className="ember-guide-image" src={selected.screenshots[0]}
       alt={'Synthetic application screenshot illustrating '+selected.title}/>}
     <div className="ember-guide-progress" aria-label={'Guide progress, step '+(stepIndex+1)+' of '+selected.steps.length}>
       {selected.steps.map((item,i)=><button type="button" key={item.id} aria-current={i===stepIndex?'step':undefined}
         aria-label={'Go to step '+(i+1)+': '+item.title}
         className={confirmed.includes(item.id)?'complete':''} onClick={()=>jump(i)}/>)}
     </div>
     <div className="ember-guide-step" key={step?.id}>
       <span>STEP {stepIndex+1} / {selected.steps.length}</span>
       <strong>{step?.title}</strong>
       <p>{step?.instruction}</p>
       {step?.writes&&<div className="ember-guide-caution">Requires a separate author action or confirmation in the application. Ember will never click it automatically.</div>}
       {workspace!==step?.workspace&&<button type="button" className="ember-guide-navigate" onClick={()=>onNavigate(step!.workspace)}>
         Open {step?.workspace} workspace ↗
       </button>}
       <button type="button" className="ember-guide-locate" onClick={locate}>Locate control on this screen</button>
       {found&&<p className="ember-guide-result" role="status">{found}</p>}
       <details><summary>Can't see the control?</summary><p>{step?.fallback}</p></details>
     </div>
     <label className="ember-guide-check"><input type="checkbox" checked={!!step&&confirmed.includes(step.id)}
       onChange={e=>setConfirmed(old=>e.target.checked?[...old,step!.id]:old.filter(id=>id!==step?.id))}/>
       I completed this step myself (not automatically verified)
     </label>
     <div className="ember-guide-controls">
       <button type="button" disabled={!stepIndex} onClick={()=>jump(stepIndex-1)}>← Back</button>
       {stepIndex+1<selected.steps.length
         ?<button type="button" onClick={()=>jump(stepIndex+1)}>Next step →</button>
         :<button type="button" onClick={()=>{setSelected(null);setFound('')}}>Finish guide</button>}
     </div>
     <p className="ember-guide-disclaimer">{selected.caution}</p>
   </div>}
 </section>
}
