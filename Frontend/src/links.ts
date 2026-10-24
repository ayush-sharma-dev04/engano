// Finding a web address inside a message the creator is drafting.

const LINK = /(?:https?:\/\/|www\.)[^\s<>"'`]+/i

/** The first web address in the text, without trailing punctuation, or null. */
export function firstLink(text: string): string | null {
  const match = text.match(LINK)
  if (!match) return null
  const url = match[0].replace(/[.,;:!?)\]}>]+$/, '')
  return url.length > 6 ? url : null
}
