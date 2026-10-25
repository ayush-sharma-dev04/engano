import type { Finding } from './App'

export type Located = { key: number; start: number; end: number; finding: Finding }

/** Where each (still visible) finding sits in the current text. Survives edits. */
export function locate(content: string, findings: Finding[], hidden: Set<number>): Located[] {
  const found: Located[] = []
  findings.forEach((finding, key) => {
    const quote = finding.quote
    if (hidden.has(key) || !quote) return
    const hint = finding.start ?? 0
    let start = -1
    if (content.slice(hint, hint + quote.length) === quote) {
      start = hint
    } else {
      for (let i = content.indexOf(quote); i !== -1; i = content.indexOf(quote, i + 1)) {
        if (start === -1 || Math.abs(i - hint) < Math.abs(start - hint)) start = i
      }
    }
    if (start >= 0) found.push({ key, start, end: start + quote.length, finding })
  })
  found.sort((a, b) => a.start - b.start || b.end - a.end)
  const result: Located[] = []
  let lastEnd = -1
  for (const item of found) {
    if (item.start >= lastEnd) {
      result.push(item)
      lastEnd = item.end
    }
  }
  return result
}
