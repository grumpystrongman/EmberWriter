import type { Workspace } from './workspace-types'

export type HelpStep = {
  id:string;title:string;instruction:string;workspace:Workspace;
  target:string;fallback:string;writes?:boolean
}
export type HelpArticle = {
  id:string;title:string;summary:string;category:string;keywords:string[];
  release:string;status:'preview'|'verified';screenshots:string[];
  prerequisites:string[];steps:HelpStep[];caution:string
}
// These steps are checked against preview control IDs. They are not yet
// stable-release certified. Guides are read-only and never click write actions.
export const HELP_ARTICLES:HelpArticle[]=[
 {
  id:'publish.epub',title:'Make an EPUB from your manuscript',
  summary:'Preview the selected Binder chapters, compile a private ebook, and locate its file.',
  category:'Publishing',release:'0.15.0-rc.2',status:'preview',
  keywords:['epub','ebook','compile','export','book files','publish','digital edition'],
  screenshots:['/help/interior-atelier.png','/help/interior-preview.png'],
  prerequisites:['Open a local story project with at least one manuscript chapter selected in the Binder.'],
  caution:'A successful local EPUB build is not retailer certification or proof that every device renders it correctly.',
  steps:[
   {id:'publish-home',title:'Open Publish',workspace:'publish',target:'.workspace-nav button[title*="Publish"],.workspace-mobile-nav button[aria-current="page"]',fallback:'Choose Publish in the primary workspace navigation.',instruction:'Go to Publish. The private Publishing Desk shows local milestones and warnings.'},
   {id:'book-files',title:'Open book interiors',workspace:'publish',target:'.pubdesk-quick-actions button:first-child',fallback:'Select Book files in Publishing Studio, or choose the Book interiors milestone and open its workspace.',instruction:'Choose Preview & compile a book to enter the Interior Atelier.'},
   {id:'preset',title:'Choose Digital edition',workspace:'publish',target:'.interioratelier-presets button:first-child',fallback:'In Book Files, select Digital edition (EPUB).',instruction:'Choose the EPUB preset. No book files are created until you confirm a build.'},
   {id:'preview',title:'Read the private preview',workspace:'publish',target:'.interioratelier-preview-button',fallback:'Choose Build / refresh private preview in the Interior Atelier.',instruction:'Generate a local preview and inspect the actual chapter text. Use the chapter selector and device simulation to inspect flow.'},
   {id:'build',title:'Prepare local EPUB',workspace:'publish',target:'.interioratelier-build',fallback:'Choose Prepare digital edition files.',instruction:'Open the build confirmation. This is still a local operation; no publisher upload happens.'},
   {id:'confirm',title:'Confirm the export',workspace:'publish',target:'.interioratelier-confirm button:first-child',fallback:'Review the listed formats and choose Confirm local build.',instruction:'Review the formats and explicitly approve local compilation.',writes:true},
   {id:'download',title:'Inspect the generated file',workspace:'publish',target:'.interioratelier-outputs a',fallback:'Use the download link displayed after a successful local compile.',instruction:'Open the resulting EPUB in a reader app and review navigation, chapter text and layout. The app cannot verify retailer acceptance.'},
  ],
 },
 {
  id:'edit.restore',title:'Revise a paragraph and restore an earlier version',
  summary:'Make one selective manuscript edit, keep the original, and learn how to recover it.',
  category:'Editing',release:'0.15.0-rc.2',status:'preview',
  keywords:['revision','restore','undo','paragraph','edit','history','version','selective'],
  screenshots:['/help/revision-workbench.png','/help/revision-confirmation.png'],
  prerequisites:['A local manuscript chapter with revision history is required.'],
  caution:'Before editing, confirm you are working on the intended manuscript and chapter. Restoring overwrites the current chapter after archiving it.',
  steps:[
   {id:'plan',title:'Open Plan',workspace:'plan',target:'.workspace-nav button[title*="Plan"]',fallback:'Choose Plan in the top navigation.',instruction:'Open the story planning workspace.'},
   {id:'edit-group',title:'Choose Edit & Review',workspace:'plan',target:'.planning-groups button',fallback:'In Plan, choose Edit & review.',instruction:'Open the author-controlled editing tools.'},
   {id:'studio',title:'Open Developmental Studio',workspace:'plan',target:'.planning-tool-tabs button',fallback:'Choose Developmental studio from the Edit & review tools.',instruction:'Select Developmental Studio.'},
   {id:'revisions',title:'Open Revision Workbench',workspace:'plan',target:'.devstudio-nav button:last-child',fallback:'Choose Revision Workbench in the editorial studio.',instruction:'Enter the side-by-side manuscript revision environment.'},
   {id:'chapter',title:'Select a chapter',workspace:'plan',target:'.devstudio-revision-toolbar select',fallback:'Choose a manuscript chapter, then open its contents.',instruction:'Select the exact chapter. Inspect its original text before drafting changes.'},
   {id:'select',title:'Select the desired edit',workspace:'plan',target:'.devstudio-paragraph input[type="checkbox"]',fallback:'Edit a paragraph and select only that change for approval.',instruction:'Write an alternative. Check only the paragraph you want to change; unchecked changes will not be saved.'},
   {id:'approve',title:'Approve after comparing',workspace:'plan',target:'.devstudio-revision-footer .devstudio-primary',fallback:'Review the selected changes and confirm explicitly.',instruction:'Confirm exactly which paragraphs will change. The old version is archived first.',writes:true},
   {id:'restore',title:'Open version history',workspace:'plan',target:'.devstudio-history summary',fallback:'Expand the Version history section.',instruction:'Expand version history. Select an earlier version only if restoration is intended.'},
   {id:'restore-confirm',title:'Confirm restoration',workspace:'plan',target:'.devstudio-confirmation .devstudio-primary',fallback:'Confirm the selected version in the separate restoration dialog.',instruction:'Restoring is a deliberate overwrite of this chapter, with the current version archived again.',writes:true},
  ],
 },
 {
  id:'series.character',title:'Explore what a character knows',
  summary:'Use the Series Desk to distinguish world truth, character beliefs and approved evidence at a book position.',
  category:'Story intelligence',release:'0.15.0-rc.2',status:'preview',
  keywords:['character','psychology','knowledge','belief','canon','series','secret'],
  screenshots:['/help/series-observatory.png'],
  prerequisites:['A Series Vault with one or more books and story entities.'],
  caution:'Literal mentions are evidence of appearance, not automatic proof of emotion or psychological development.',
  steps:[
   {id:'series',title:'Open Series Desk',workspace:'series',target:'.series-experience-modes button:first-child',fallback:'Choose Series from the navigation and select your series.',instruction:'Select the series and enter Explore.'},
   {id:'character',title:'Choose Character Minds',workspace:'series',target:'.observatory-lenses button',fallback:'In Story Observatory, select Character Minds.',instruction:'Compare grounded character knowledge and beliefs with the story world.'},
   {id:'evidence',title:'Inspect an original source',workspace:'series',target:'.story-observatory button',fallback:'Select a visible assertion or citation in the Observatory.',instruction:'Open a cited source before deciding whether the fact belongs in approved canon.'},
   {id:'review',title:'Review any pending assertion',workspace:'series',target:'.series-experience-modes button:nth-child(3)',fallback:'Choose Verify and Review canon.',instruction:'Only deliberate author approval changes proposed canon. Never approve a claim without inspecting its evidence.',writes:true},
  ],
 },
 {
  id:'scene.direct',title:'Plan a scene and send its brief to Writer',
  summary:'Build a storyboard, save it, and move the directing brief into Scene Writer without editing the manuscript.',
  category:'Scene craft',release:'0.15.0-rc.2',status:'preview',
  keywords:['scene','director','beats','tension','cast','handoff','writer','storyboard'],
  screenshots:['/help/series-observatory.png'],
  prerequisites:['A Series Vault with a book and scene board.'],
  caution:'Sending a brief prepares a prompt only. It is not a generated chapter or approved canon; any generation must be initiated separately.',
  steps:[
   {id:'series',title:'Open Series',workspace:'series',target:'.series-experience-modes button:nth-child(2)',fallback:'Choose Series, then Direct.',instruction:'Enter the Character & Scene Studio under Direct.'},
   {id:'director',title:'Choose Scene Director',workspace:'series',target:'.p2-studio button',fallback:'Choose Scene Director and open or create a board.',instruction:'Inspect the scene objective, obstacles, POV, location, cast and beat timeline.'},
   {id:'save',title:'Save the board',workspace:'series',target:'.p2-board-actions button:first-child',fallback:'Save the scene plan before continuing.',instruction:'Save your changes to the scene board so the handoff uses an identified version.',writes:true},
   {id:'send',title:'Choose Send to Scene Writer',workspace:'series',target:'.p2-board-actions button:nth-child(2)',fallback:'Choose Send to Scene Writer, which is enabled for a saved, unchanged scene board.',instruction:'Open the directing brief handoff confirmation.'},
   {id:'confirm',title:'Confirm the non-destructive handoff',workspace:'series',target:'.p2-handoff-confirm button:first-of-type',fallback:'Review the confirmation and choose Open Scene Writer with brief.',instruction:'Approve navigating to Scene Writer with the saved planning brief. No manuscript write or generation occurs.',writes:true},
  ],
 },
 {
  id:'publishing.recovery',title:'Protect and recover your manuscript',
  summary:'Find the Recovery Center and understand local checkpoints and safe restore behavior.',
  category:'Safety',release:'0.15.0-rc.2',status:'preview',
  keywords:['backup','restore','recovery','checkpoint','copy','archive','safety'],
  screenshots:[],
  prerequisites:['A local project and backup destination.'],
  caution:'Test restoration using a disposable synthetic project first. Keep an independent offline copy of your real manuscript.',
  steps:[
   {id:'recovery',title:'Open Recovery Center',workspace:'write',target:'.workspace-recovery-button',fallback:'Use Local backup or Protect work in the top toolbar.',instruction:'Open Recovery Center; it shows the status of protected copies and recovery options.'},
   {id:'snapshot',title:'Inspect available copies',workspace:'write',target:'.recovery-center',fallback:'Review local checkpoints and external backup options.',instruction:'Check that an independent, recent copy exists. A local snapshot on the same drive is not a complete disaster recovery plan.'},
   {id:'restore',title:'Review recovery confirmation',workspace:'write',target:'.recovery-center',fallback:'Follow the separate confirmation in Recovery Center.',instruction:'Before restoring, verify the exact project, date and target. Recovery can replace files and requires explicit user approval.',writes:true},
  ],
 },
]

function terms(value:string){return value.toLowerCase().match(/[a-z0-9]+/g)||[]}
export function searchHelp(query:string):HelpArticle[]{
 const ignored=new Set(["how","can","please","show","me","you","a","an","the","to","for","with","and","in","on","my","is","do","does","what","where","about","of","from","it","through"])
 const q=terms(query).filter(word=>word.length>=3&&!ignored.has(word))
 if(!q.length)return HELP_ARTICLES
 return HELP_ARTICLES.map(article=>{
   const title=article.title.toLowerCase()
   const words=article.keywords.join(' ').toLowerCase()
   const summary=article.summary.toLowerCase()
   const score=q.reduce((n,term)=>n+(title.includes(term)?6:0)+(words.includes(term)?4:0)+(summary.includes(term)?2:0),0)
   return {article,score}
 }).filter(item=>item.score>0).sort((a,b)=>b.score-a.score).map(item=>item.article)
}
