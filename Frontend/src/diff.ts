export type Piece = { kind: 'same' | 'add' | 'del'; text: string }

/**
 * Word-level difference between two texts: what was removed from `before` and what was added in
 * `after`. Whitespace is kept so the pieces join back into either text. Very long texts fall back
 * to "all removed, all added" rather than freezing the page.
 */
export function wordDiff(before: string, after: string): Piece[] {
  const a = before.split(/(\s+)/).filter((t) => t !== '')
  const b = after.split(/(\s+)/).filter((t) => t !== '')

  // Most edits touch the middle of a text: peel off what both versions share at each end first.
  let head = 0
  while (head < a.length && head < b.length && a[head] === b[head]) head++
  let tail = 0
  while (tail < a.length - head && tail < b.length - head && a[a.length - 1 - tail] === b[b.length - 1 - tail]) tail++
  const midA = a.slice(head, a.length - tail)
  const midB = b.slice(head, b.length - tail)

  const out: Piece[] = []
  const push = (kind: Piece['kind'], text: string) => {
    if (!text) return
    const last = out[out.length - 1]
    if (last && last.kind === kind) last.text += text
    else out.push({ kind, text })
  }
  push('same', a.slice(0, head).join(''))

  if (midA.length * midB.length > 6_000_000) {
    // Too different to compare word by word: show it as replaced rather than freezing the page.
    push('del', midA.join(''))
    push('add', midB.join(''))
  } else {
    // Longest common subsequence of the differing middle.
    const cols = midB.length + 1
    const table = new Uint32Array((midA.length + 1) * cols)
    for (let i = midA.length - 1; i >= 0; i--) {
      for (let j = midB.length - 1; j >= 0; j--) {
        table[i * cols + j] =
          midA[i] === midB[j] ? table[(i + 1) * cols + j + 1] + 1 : Math.max(table[(i + 1) * cols + j], table[i * cols + j + 1])
      }
    }
    let i = 0
    let j = 0
    while (i < midA.length && j < midB.length) {
      if (midA[i] === midB[j]) {
        push('same', midA[i])
        i++
        j++
      } else if (table[(i + 1) * cols + j] >= table[i * cols + j + 1]) {
        push('del', midA[i++])
      } else {
        push('add', midB[j++])
      }
    }
    while (i < midA.length) push('del', midA[i++])
    while (j < midB.length) push('add', midB[j++])
  }

  push('same', a.slice(a.length - tail).join(''))
  return out
}
