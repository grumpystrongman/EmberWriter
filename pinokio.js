"use strict";
// Pinokio 8 preview launcher. Not approved for public Discover until a real
// fresh-install and preservation drill is performed inside Pinokio itself.
module.exports = {
  version: "8.0.0",
  title: "EmberWriter — Author-First Writing Studio",
  description: "Write novels, manage story canon, direct local narration and protect your books.",
  link: "https://github.com/grumpystrongman/EmberWriter",
  menu: async (_kernel, info) => {
    const source = [
      { text: "View source and documentation", icon: "fa-brands fa-github",
        href: "https://github.com/grumpystrongman/EmberWriter", popout: true },
      { text: "Watch the 10-minute demo", icon: "fa-solid fa-film",
        href: "https://github.com/grumpystrongman/EmberWriter/releases/tag/emberwriter-author-first-demo-2026-11-07",
        popout: true },
    ];
    // Avoid assuming Pinokio installed a Python runtime: this app currently
    // requires a Windows Python 3.11 launcher and Node/npm for install.ps1.
    const installed = info.exists("backend/.venv/Scripts/python.exe")
      && info.exists("frontend/node_modules/.bin/vite.cmd");
    if (!installed) {
      return [
        { text: "Install writer-only (no models)", icon: "fa-solid fa-download",
          href: "pinokio-install.js" },
        ...source,
      ];
    }
    return [
      { text: "Start EmberWriter", icon: "fa-solid fa-play", href: "pinokio-start.js" },
      ...(info.running("pinokio-start.js")
        ? [{ text: "Open writing studio", icon: "fa-solid fa-pen-nib",
             href: "http://127.0.0.1:5173" }] : []),
      { text: "Repair writer-only installation", icon: "fa-solid fa-screwdriver-wrench",
        href: "pinokio-install.js" },
      ...source,
    ];
  },
};
