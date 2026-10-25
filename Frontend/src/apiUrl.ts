// Where the ENGANO backend is. The web app can be hosted anywhere (Netlify) while the backend runs on
// someone's computer behind a tunnel whose address changes, so the address can be set in the browser.
const KEY = 'engano_api_url'

const BUILT_IN = ((import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000').replace(/\/+$/, '')

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])

/** A clean origin (https://host or http://localhost:port), or null if this is not an address we will talk to. */
export function normalizeApi(raw: string): string | null {
  let url: URL
  try {
    url = new URL(raw.trim())
  } catch {
    return null
  }
  if (url.username || url.password) return null
  if (url.protocol === 'https:') return url.origin
  // Plain http only for this computer: a hosted (https) page may not call other http addresses anyway.
  if (url.protocol === 'http:' && LOCAL_HOSTS.has(url.hostname)) return url.origin
  return null
}

/** The backend address in use: the one saved in this browser, else the one built in. */
export function apiBase(): string {
  try {
    const saved = localStorage.getItem(KEY)
    const clean = saved ? normalizeApi(saved) : null
    if (clean) return clean
  } catch {
    /* storage blocked: use the built-in address */
  }
  return BUILT_IN
}

export function saveApi(raw: string): boolean {
  const clean = normalizeApi(raw)
  if (!clean) return false
  try {
    if (clean === BUILT_IN) localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, clean)
    return true
  } catch {
    return false
  }
}

export function resetApi(): void {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* nothing saved */
  }
}

export const builtInApi = BUILT_IN

/**
 * An address offered by a link (?api=https://...). It is only ever a suggestion: the person must confirm it,
 * because a stranger's link must not be able to quietly point the app (and the passwords typed into it) elsewhere.
 */
export function proposedApi(search: string = typeof location === 'undefined' ? '' : location.search): string | null {
  const given = new URLSearchParams(search).get('api')
  const clean = given ? normalizeApi(given) : null
  return clean && clean !== apiBase() ? clean : null
}
