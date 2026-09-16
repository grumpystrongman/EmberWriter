import { useEffect } from 'react'

function cleanText(value: string | null | undefined) {
  return (value || '').replace(/\s+/g, ' ').trim().toLowerCase()
}

function selectFreshWriteMode() {
  const writeButton = Array.from(document.querySelectorAll<HTMLButtonElement>('.mode-grid button'))
    .find((button) => cleanText(button.textContent) === 'write')
  if (writeButton && !writeButton.classList.contains('active')) writeButton.click()
}

/**
 * Continue is intentionally one-shot.
 *
 * The legacy Write rail historically defaulted to Continue and kept that mode selected after a
 * generation. That made a later prompt inherit the previous manuscript ending even when the author
 * never asked to continue. Fresh Write is now restored whenever a project opens and immediately
 * after a generation request has captured its selected mode. An author who wants continuation can
 * still click Continue for that specific request.
 */
export default function GenerationModePolicy() {
  useEffect(() => {
    let lastProject = ''
    let resetTimer = 0

    function scheduleFreshMode(delay = 0) {
      window.clearTimeout(resetTimer)
      resetTimer = window.setTimeout(selectFreshWriteMode, delay)
    }

    function detectProjectChange() {
      const activeProject = document.querySelector<HTMLElement>('.project-card.active strong')
      const projectName = cleanText(activeProject?.textContent)
      if (!projectName || projectName === lastProject) return
      lastProject = projectName
      scheduleFreshMode(100)
    }

    function onClick(event: MouseEvent) {
      const element = event.target instanceof Element ? event.target : null
      const button = element?.closest<HTMLButtonElement>('.assistant button.primary')
      if (!button || cleanText(button.textContent) !== 'generate') return

      // React handles the click first and captures the current mode for this request. Reset on the
      // next task so Continue does not silently leak into the author's next generation.
      scheduleFreshMode(0)
    }

    const observer = new MutationObserver(detectProjectChange)
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] })
    document.addEventListener('click', onClick)
    detectProjectChange()
    scheduleFreshMode(150)

    return () => {
      window.clearTimeout(resetTimer)
      observer.disconnect()
      document.removeEventListener('click', onClick)
    }
  }, [])

  return null
}
