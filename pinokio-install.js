"use strict";
// Explicit lean setup: NEVER automatically download any writing/image/voice
// model. Never reset/delete an author data folder.
module.exports = {
  version: "8.0.0",
  run: [{
    when: "{{platform === 'win32'}}",
    method: "shell.run",
    params: {
      path: ".",
      message: "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\install.ps1 -SkipModelDownload -SkipImageEngineInstall -SkipImageModelDownload",
    },
  }, {
    when: "{{platform !== 'win32'}}",
    method: "notify",
    params: {
      html: "This preview launcher requires Windows. No software was installed or manuscript data touched.",
    },
  }],
};
