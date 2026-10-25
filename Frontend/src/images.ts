// Reading images the creator attaches to a draft (kept in the browser until a review is run).

export type AttachedImage = {
  id: string
  name: string
  preview: string // data URL, for the thumbnail
  data: string // base64 file contents, sent to the backend
  alt: string
}

export const MAX_IMAGES = 4
export const MAX_IMAGE_BYTES = 4 * 1024 * 1024
const TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif']

/** Why a file can't be attached, or null if it can. */
export function problemWith(file: File, alreadyAttached: number): string | null {
  if (alreadyAttached >= MAX_IMAGES) return `You can attach up to ${MAX_IMAGES} images.`
  if (!TYPES.includes(file.type)) return `${file.name || 'That file'} isn't a PNG, JPEG, WebP or GIF image.`
  if (file.size > MAX_IMAGE_BYTES) return `${file.name || 'That image'} is over 4 MB.`
  return null
}

export function readImage(file: File): Promise<AttachedImage> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`Couldn't read ${file.name || 'that image'}.`))
    reader.onload = () => {
      const url = String(reader.result)
      resolve({
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        name: file.name || 'pasted image',
        preview: url,
        data: url.slice(url.indexOf(',') + 1),
        alt: '',
      })
    }
    reader.readAsDataURL(file)
  })
}
