const FOLDER_INPUT_SELECTOR = '.load-import-card input.hidden-file-input[type="file"][multiple]:not([accept])'

function applyFolderDirectoryMode() {
  document.querySelectorAll<HTMLInputElement>(FOLDER_INPUT_SELECTOR).forEach((input) => {
    input.setAttribute('webkitdirectory', '')
    input.setAttribute('directory', '')
  })
}

function installFolderDirectoryMode() {
  applyFolderDirectoryMode()
  const observer = new MutationObserver(() => applyFolderDirectoryMode())
  observer.observe(document.documentElement, { childList: true, subtree: true })
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', installFolderDirectoryMode, { once: true })
} else {
  installFolderDirectoryMode()
}
