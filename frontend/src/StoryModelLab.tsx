import { useEffect, useState } from 'react'
import './story-model-lab.css'

type SceneReport = {
  scenario_id: string
  name: string
  word_count: number
  paragraph_count: number
  passed: boolean
  elapsed_seconds: number | null
  missing_elements: string[]
  forbidden_reveals: string[]
  repeated_5grams: [string, number][]
  signals: Record<string, boolean>
}
type Job = {
  status: 'not_run' | 'queued' | 'running' | 'completed' | 'failed' | 'interrupted'
  id?: string; model?: string; error?: string; local_only: boolean
  completed_scenarios?: number; total_scenarios?: number
  latest_scenario?: {name: string; passed: boolean}
  result?: { model: string; passed: number; total: number; passing_fraction: number; scenarios: SceneReport[]; generated_at: string }
}
const API='http://127.0.0.1:8000/api'
const scenarioDetails=[
  {icon:'◈',name:'Character Knowledge',detail:'Does the model respect what characters do and do not know?'},
  {icon:'◇',name:'Setup & Payoff',detail:'Does an introduced clue return in a causally connected outcome?'},
  {icon:'✦',name:'Lasting Consequences',detail:'Does a decision create a meaningful aftermath?'},
]
const descriptions:Record<string,string>={
  nonempty:'Model produced text',
  length:'Scene length within target range',
  named_elements:'Required characters and objects appeared',
  no_forbidden_reveal:'No explicit forbidden phrase appeared',
  no_high_5gram_repetition:'No highly repeated five-word sequences',
  narrative_format:'Paragraph-based prose rather than an outline',
}
export default function StoryModelLab({seriesId}:{seriesId:string}){
  const [models,setModels]=useState<string[]>([])
  const [modelsLoading,setModelsLoading]=useState(true)
  const [model,setModel]=useState('')
  const [job,setJob]=useState<Job>({status:'not_run',local_only:true})
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(false)
  useEffect(()=>{
    let alive=true
    void Promise.all([
      fetch(`${API}/series/${encodeURIComponent(seriesId)}/model-evaluation`).then(r=>r.json()),
      fetch(`${API}/models`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({provider:'ollama',base_url:'http://127.0.0.1:11434',model:''}),
      }).then(r=>r.ok?r.json():{models:[]}),
    ]).then(([status,available]:[Job,{models?:string[]}])=>{
      if(!alive)return
      const local=(available.models||[]).filter(name=>!/(?:^|[-:])(cloud|remote)(?:$|[-:])/i.test(name))
      setModels(local);setModelsLoading(false);setModel(local.includes('llama3.2:3b')?'llama3.2:3b':local[0]||'');setJob(status)
    }).catch(e=>{if(alive){setError(String(e));setModelsLoading(false)}})
    return()=>{alive=false}
  },[seriesId])
  useEffect(()=>{
    if(job.status!=='queued'&&job.status!=='running')return
    let active=true
    const timer=setInterval(()=>{
      void fetch(`${API}/series/${encodeURIComponent(seriesId)}/model-evaluation`)
        .then(r=>r.json()).then((result:Job)=>{if(active)setJob(result)})
        .catch(()=>{})
    },2000)
    return()=>{active=false;clearInterval(timer)}
  },[seriesId,job.status])
  async function begin(){
    if(!model||loading)return
    setLoading(true);setError('')
    try{
      const response=await fetch(`${API}/series/${encodeURIComponent(seriesId)}/model-evaluation`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model}),
      })
      const result=await response.json()
      if(!response.ok)throw Error(result.detail||'Could not begin local model evaluation')
      setJob(result)
    }catch(e){setError(String(e))}
    finally{setLoading(false)}
  }
  const running=job.status==='queued'||job.status==='running'
  const completed=job.result
  const count=job.completed_scenarios||0
  return <section className="story-model-lab" aria-label="Local generation quality laboratory">
    <header className="model-lab-heading"><span>THE PROSE TEST KITCHEN · LOCAL ONLY</span><h3>Trust the model. Test the model.</h3>
      <p>Before relying on an AI for your novel, challenge it with three synthetic, repeatable writing tasks. No manuscript passages leave your machine or enter this test.</p></header>
    <div className="model-lab-scenarios">{scenarioDetails.map((scenario,i)=>
      <article key={scenario.name} className="model-lab-scenario">
        <span>{scenario.icon}</span><small>TEST 0{i+1}</small><strong>{scenario.name}</strong><p>{scenario.detail}</p>
      </article>)}</div>
    <div className="model-lab-console">
      <div><h4>Run the local benchmark</h4><p>Three scenes, 280–420 requested words each. Results measure concrete signals—not literary greatness.</p></div>
      <div className="model-lab-actions">
        <label>Installed local model
          <select aria-label="Installed local model" value={model} onChange={e=>setModel(e.target.value)} disabled={running}>
            {!models.length&&<option value="">{modelsLoading?'Checking local models…':'No local Ollama models detected'}</option>}
            {models.map(item=><option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <button type="button" disabled={!model||running||loading} onClick={()=>void begin()}>
          {running?'Testing local model…':loading?'Starting…':'▶ Run three-scene test'}
        </button>
      </div>
    </div>
    {error&&<div className="model-lab-error" role="alert">{error}</div>}
    {job.error&&<div className="model-lab-error" role="alert">{job.error}</div>}
    {running&&<div className="model-lab-progress" role="status">
      <div><strong>Evaluating {job.model}</strong><span>{count} of {job.total_scenarios||3} scenes complete</span></div>
      <div className="model-lab-progress-track"><span style={{width:`${Math.round((count/(job.total_scenarios||3))*100)}%`}}/></div>
      <p>All generation runs through your installed local Ollama. Leaving this view does not cancel a submitted evaluation.</p>
    </div>}
    {completed&&<div className="model-lab-results">
      <div className="model-lab-result-summary"><strong>{completed.passed}<span>/{completed.total}</span></strong>
        <div><h4>Checks passed</h4><p>{completed.model} · {new Date(completed.generated_at).toLocaleString()}</p></div></div>
      <div className="model-lab-result-grid">{completed.scenarios.map(s=>
        <article key={s.scenario_id} className={s.passed?'is-pass':'is-issue'}>
          <header><span>{s.passed?'✓ Met checks':'! Review warnings'}</span><h4>{s.name}</h4></header>
          <div className="model-lab-metrics"><strong>{s.word_count}<small> words</small></strong>
            <strong>{s.paragraph_count}<small> paragraphs</small></strong>
            <strong>{s.elapsed_seconds?.toFixed(1)||'—'}<small> seconds</small></strong></div>
          <div className="model-lab-signals">{Object.entries(s.signals).map(([name,pass])=>
            <span key={name} className={pass?'pass':'fail'}>{pass?'✓':'×'} {descriptions[name]||name}</span>)}</div>
          {s.missing_elements.length>0&&<p>Missing: {s.missing_elements.join(', ')}</p>}
          {s.repeated_5grams.length>0&&<p>Repeated phrase: {s.repeated_5grams[0][0]}</p>}
        </article>)}</div>
    </div>}
    {job.status==='not_run'&&<div className="model-lab-empty">Select an installed model and run the benchmark to establish your first reproducible baseline.</div>}
    <footer>Benchmark outcomes are diagnostic indicators. Human review still determines character authenticity, emotional impact, creativity and manuscript readiness. No generated content is automatically inserted into your book.</footer>
  </section>
}
