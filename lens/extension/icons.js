export function icon(name) {
  const paths = {
    lens: '<circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5M10 6.5v7M6.5 10h7"/>',
    arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
    external: '<path d="M14 4h6v6m0-6L10 14M10 4H4v16h16v-6"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    minus: '<path d="M5 12h14"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 6M4 12l2 6a7 7 0 0 0 12-1"/>',
    settings: '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor"/><circle cx="15" cy="17" r="3" fill="currentColor"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    book: '<path d="M4 4h6l2 2 2-2h6v15h-6l-2 2-2-2H4zM12 6v15"/>',
  };
  return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.lens}</svg>`;
}
