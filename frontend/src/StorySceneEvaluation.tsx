import {useEffect,useMemo,useState} from 'react'
import ReviewQueue from './ReviewQueue'
import type {QueueRow} from './ReviewQueue'
import './story-scene-evaluation.css'

type GoldCase={
 id:string;label:string;gold_scene_boundary:boolean;candidate_boundary_at_gold:boolean;
 candidate_break_count:number;extraneous_breaks:number;gold_boundary_offset:number|null;
 boundary_result:string;gold_pov:string;predicted_pov:string;pov_grading:string;
 gold_character_knowledge:string;predicted_character_knowledge:string;
 knowledge_grading:string;annotation:string;synthetic_preview:string
}
type Report={
 dataset:string;case_count:number;boundary:{true_positive:number;false_positive:number;
 false_negative:number;true_negative:number;precision:number;recall:number;f1:number};
 pov:{gold_cases:number;prediction_coverage:number;correct_predictions:number};
 character_knowledge:{gold_known_cases:number;prediction_coverage:number;correct_predictions:number};
 cases:GoldCase[];scene_interpretation_gate:string;automatic_scene_approval_allowed:boolean;
 source_text_sent:boolean;external_model_calls:boolean;limitations:string;
 author_reviews:{shown:number;pending:number;author_confirmed_scenes:number;
 source_verified:number;limited_to_first:number;cannot_be_used_as_gold_automatically:boolean}
}
const BASE='http://127.0.0.1:8000/api/series'

export default function StorySceneEvaluation({seriesId,book,revision=0}:{
 seriesId:string;book:number;revision?:number
}){
 const [open,setOpen]=useState(false)
 const [report,setReport]=useState<Report|null>(null)
 const [error,setError]=useState('')
 const [loading,setLoading]=useState(false)
 useEffect(()=>{
  const ctrl=new AbortController()
  setReport(null);setError('')
  if(!open)return
  setLoading(true)
  void fetch(`${BASE}/${encodeURIComponent(seriesId)}/scene-evaluation?book=${book}`,
   {signal:ctrl.signal})
   .then(async r=>{if(!r.ok)throw Error('Literary evaluation fixture could not be read');return r.json() as Promise<Report>})
   .then(data=>{if(!ctrl.signal.aborted)setReport(data)})
   .catch(reason=>{if(!ctrl.signal.aborted)setError(String(reason))})
   .finally(()=>{if(!ctrl.signal.aborted)setLoading(false)})
  return()=>ctrl.abort()
 },[open,seriesId,book,revision])
 const rows=useMemo<QueueRow[]>(()=>report?.cases.map(test=>({
  key:test.id,title:test.label,
  subtitle:'Gold: '+(test.gold_scene_boundary?'scene changes':'scene continues')+
    ' · Navigation: '+(test.candidate_boundary_at_gold?'boundary at gold position':'no boundary at gold position'),
  preview:test.annotation,status:test.boundary_result.replaceAll('_',' '),
  meta:test.extraneous_breaks?'Extra splits '+test.extraneous_breaks:'No extra splits',
 }))||[],[report])
 function detail(row:QueueRow){
  const test=report?.cases.find(x=>x.id===row.key)
  if(!test)return null
  return <div className="scene-evaluation-inspector">
   <h4>{test.label}</h4>
   <blockquote>{test.synthetic_preview}</blockquote>
   <p><strong>Predeclared narrative annotation:</strong> {test.annotation}</p>
   <dl>
    <dt>Author-defined gold boundary</dt><dd>{test.gold_scene_boundary?'Yes':'No'}</dd>
    <dt>Reading-window boundary aligned</dt><dd>{test.candidate_boundary_at_gold?'Yes':'No'}</dd>
    <dt>Extraneous navigation splits</dt><dd>{test.extraneous_breaks}</dd>
    <dt>Gold viewpoint</dt><dd>{test.gold_pov.replaceAll('_',' ')}</dd>
    <dt>Current viewpoint inference</dt><dd>Abstained — not implemented</dd>
    <dt>Character-knowledge interpretation</dt><dd>Abstained — not implemented</dd>
   </dl>
   <p>All example passages here are synthetic fixtures. A coincidentally aligned reading window does not establish a real scene or POV interpretation.</p>
  </div>
 }
 return <details className="story-scene-evaluation" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
  <summary>Literary interpretation quality gate · synthetic gold tests</summary>
  {open&&<>
   <p>The candidate segmenter is being graded against predeclared scene boundaries. This is a safety diagnostic, not a model certification or an author-grade scene detector.</p>
   {error&&<p role="alert">{error}</p>}
   {loading&&<p role="status">Checking 12 local fictional cases…</p>}
   {report&&<>
    <div className="scene-evaluation-summary" aria-label="Gold evaluation metrics">
     <div><small>Boundary precision</small><strong>{Math.round(report.boundary.precision*100)}%</strong></div>
     <div><small>Boundary recall</small><strong>{Math.round(report.boundary.recall*100)}%</strong></div>
     <div><small>Boundary F1</small><strong>{Math.round(report.boundary.f1*100)}%</strong></div>
     <div><small>POV / knowledge predictions</small><strong>{report.pov.prediction_coverage} / {report.character_knowledge.prediction_coverage}</strong></div>
    </div>
    <p className="scene-evaluation-gate" role="status">
     <strong>Not certified for automatic scene interpretation.</strong>
     {' '}{report.boundary.true_positive} matched breaks; {report.boundary.false_positive} extra splits;
     {' '}{report.boundary.false_negative} missed scene changes. All viewpoint and knowledge claims abstain.
    </p>
    <ReviewQueue title={'Literary boundary stress tests · '+report.case_count+' fixtures'}
     description="Inspect the fictional reference passage and predeclared expected interpretation for each local synthetic case."
     rows={rows} detail={detail} emptyText="No gold-standard cases available."/>
    <p className="scene-evaluation-author">
     Book {book}: {report.author_reviews.shown} authored review records shown,
     {' '}{report.author_reviews.author_confirmed_scenes} confirmed scenes,
     {' '}{report.author_reviews.pending} awaiting classification.
     These are not silently recycled into evaluation gold.
    </p>
    <p className="scene-evaluation-limitations">{report.limitations}</p>
   </>}
  </>}
 </details>
}
