"use strict";
// Data is outside the downloadable project; updates cannot overwrite it.
// The underlying start.ps1 stops services on fixed ports, so a separate
// protective preflight refuses startup when the ports are occupied.
module.exports = {
  version: "8.0.0",
  daemon: true,
  run: [{
    when: "{{platform === 'win32'}}",
    method: "shell.run",
    params: {
      path: ".",
      message: "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\pinokio-launch-windows.ps1",
    },
  }],
};
