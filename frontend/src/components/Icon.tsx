const paths = {
  document: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h6",
  book: "M12 5v16 M3 3h5a4 4 0 0 1 4 2 4 4 0 0 1 4-2h5v16h-5a4 4 0 0 0-4 2 4 4 0 0 0-4-2H3z",
  history: "M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v5l3 2",
  user: "M20 21v-2a6 6 0 0 0-6-6h-4a6 6 0 0 0-6 6v2 M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  shield: "M12 2 3 6v6c0 6 9 10 9 10s9-4 9-10V6z M8 12l3 3 5-6",
  logout: "M9 21H4V3h5 M9 12h12 M17 8l4 4-4 4",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  eye: "M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0",
  spark: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z",
  copy: "M8 8h12v13H8z M16 8V3H3v13h5",
  mail: "M3 6h18v12H3z M3.4 6.5 12 13l8.6-6.5",
  lock: "M5 11h14v10H5z M8 11V8a4 4 0 0 1 8 0v3 M12 15v2",
  leaf: "M20 4c0 9-5 14-13 14 0-9 5-14 13-14 M7 18c1-5 4-8 9-10",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18 M12 11v5 M12 8h.01",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18 M3.6 9h16.8 M3.6 15h16.8 M12 3c2.5 2.6 2.5 15.4 0 18 M12 3c-2.5 2.6-2.5 15.4 0 18",
} as const;
export type IconName = keyof typeof paths;
export function Icon({ name }: { name: IconName }) {
  return <svg className="ui-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
