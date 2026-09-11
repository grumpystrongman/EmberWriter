export type Workspace = 'write' | 'plan' | 'characters' | 'world' | 'analyze' | 'publish' | 'submit'

export type WorkspaceProject = {
  slug: string
  name: string
  description: string
  activePath: string
}

export type ProviderConfig = {
  provider: 'ollama' | 'openai_compatible'
  base_url: string
  model: string
  api_key?: string
}
