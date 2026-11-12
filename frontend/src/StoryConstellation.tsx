import { useMemo } from 'react'
import type { CSSProperties } from 'react'

type Entity = { id: string; name: string; kind: string }
type Link = { from: string; to: string; predicate: string; fact_id: string; scope: string; relationship: boolean }
const colors: Record<string,string> = {
  character:'#c5a7f2',artifact:'#e7be83',place:'#73c8bb',faction:'#8cafee',
  event:'#e7dd8c',rule:'#f1a5a9',species:'#d2b7a1',concept:'#93bbdb',
}
const symbols: Record<string,string> = {character:'♙',artifact:'◇',place:'⌖',faction:'⚑',event:'◈',rule:'✧'}
const colorFor = (kind:string)=>colors[kind]||'#a8bcd0'

export default function StoryConstellation({entities, selectedId, links, factCounts, onSelect}:{
  entities:Entity[]; selectedId:string|null; links:Link[]
  factCounts: Record<string,number>
  onSelect:(id:string)=>void
}) {
  const display=entities.slice(0,18)
  const layout=useMemo(()=>{
    const center=display.find(item=>item.id===selectedId)||display[0]
    const ring=display.filter(item=>item.id!==center?.id)
    const innerCount=Math.min(ring.length,8)
    const outerCount=Math.max(0,ring.length-8)
    const nodes=center?[{...center,x:500,y:325,center:true}]:[]
    for(let i=0;i<ring.length;i++){
      const outer=i>=8
      const ordinal=outer?i-8:i
      const count=outer?outerCount:innerCount
      const angle=(2*Math.PI*ordinal/Math.max(1,count))-Math.PI/2+(outer?Math.PI/Math.max(count,1):0)
      nodes.push({...ring[i],x:500+Math.cos(angle)*(outer?430:295),
        y:325+Math.sin(angle)*(outer?280:220),center:false})
    }
    // Relax overlapping constellation cards deterministically. The original
    // two-ring placement allowed nearby inner/outer nodes to cover each other,
    // hiding story entities on medium-width desktops.
    for(let step=0;step<100;step++){
      let collisions=0
      for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
        const a=nodes[i],b=nodes[j]
        const deltaX=b.x-a.x,deltaY=b.y-a.y
        const requiredX=(a.center||b.center)?205:172
        const requiredY=(a.center||b.center)?155:138
        const overlapX=requiredX-Math.abs(deltaX)
        const overlapY=requiredY-Math.abs(deltaY)
        if(overlapX<=0||overlapY<=0)continue
        collisions++
        const directionX=deltaX===0?(i<j?1:-1):Math.sign(deltaX)
        const directionY=deltaY===0?(i<j?1:-1):Math.sign(deltaY)
        const moveX=overlapX/requiredX<=overlapY/requiredY
        const delta=(moveX?overlapX:overlapY)+3
        const fractionA=a.center?0:b.center?1:0.5
        const fractionB=b.center?0:a.center?1:0.5
        if(moveX){a.x-=directionX*delta*fractionA;b.x+=directionX*delta*fractionB}
        else{a.y-=directionY*delta*fractionA;b.y+=directionY*delta*fractionB}
      }
      for(const node of nodes){
        if(node.center)continue
        node.x=Math.max(95,Math.min(905,node.x))
        node.y=Math.max(70,Math.min(580,node.y))
      }
      if(!collisions)break
    }
    return nodes
  },[display.map(item=>item.id).join('|'),selectedId])
  const map=new Map(layout.map(item=>[item.id,item]))
  const relevantLinks=links.filter(link=>map.has(link.from)&&map.has(link.to))
  return <div className="observatory-network" aria-label="Interactive graph of cited story relationships">
    <div className="observatory-network-stars" aria-hidden="true"/>
    <svg className="observatory-network-edges" viewBox="0 0 1000 650" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="observatory-link" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#bd9acc" stopOpacity=".7"/>
          <stop offset="1" stopColor="#6a9caa" stopOpacity=".5"/>
        </linearGradient>
      </defs>
      {relevantLinks.map((edge,i)=>{
        const a=map.get(edge.from)!,b=map.get(edge.to)!
        const active=a.id===selectedId||b.id===selectedId
        return <line key={edge.fact_id+'-'+i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
          stroke={active?'#e7bbda':'url(#observatory-link)'}
          strokeWidth={active?3:1.5} opacity={active ? 0.9 : 0.35}/>
      })}
    </svg>
    {layout.map(node=><button type="button" key={node.id}
      className={['observatory-graph-node',node.center?'is-center':'',node.id===selectedId?'is-selected':''].join(' ')}
      style={{'--graph-color':colorFor(node.kind),left:node.x/10+'%',top:node.y/6.5+'%'} as CSSProperties}
      aria-pressed={node.id===selectedId} aria-label={node.name+', '+node.kind+', '+(factCounts[node.id]||0)+' facts'}
      onClick={()=>onSelect(node.id)}>
      <span className="observatory-graph-symbol" aria-hidden="true">{symbols[node.kind]||'✦'}</span>
      <strong>{node.name}</strong><small>{node.kind} · {factCounts[node.id]||0}</small>
    </button>)}
    <div className="observatory-network-footnote">Connections reflect approved, explicitly linked story facts. Unconnected nodes have no invented edges.</div>
  </div>
}
