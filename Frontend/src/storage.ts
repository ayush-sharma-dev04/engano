import { useCallback, useEffect, useState } from 'react'

const storeFor = (area: 'local' | 'session') => (area === 'local' ? localStorage : sessionStorage)

/**
 * State that survives a refresh. By default it is kept in this browser (localStorage) and
 * follows changes made in other tabs, so a Brand Manager tab and a Creator tab see the same
 * workspaces. With area "session" it belongs to one tab (used for who is signed in).
 * Reads and writes never throw: with storage blocked the app still works for the session.
 */
export function usePersisted<T>(key: string, initial: T, area: 'local' | 'session' = 'local') {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = storeFor(area).getItem(key)
      return raw ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })

  useEffect(() => {
    try {
      storeFor(area).setItem(key, JSON.stringify(value))
    } catch {
      /* storage unavailable: keep working in memory */
    }
  }, [key, value, area])

  useEffect(() => {
    // A tab's own storage (sessionStorage) is never shared, so there is nothing to follow.
    if (area !== 'local') return
    const onStorage = (event: StorageEvent) => {
      if (event.storageArea !== localStorage || event.key !== key || event.newValue === null) return
      try {
        setValue(JSON.parse(event.newValue) as T)
      } catch {
        /* ignore a value we cannot read */
      }
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [key, area])

  const update = useCallback((next: T | ((current: T) => T)) => setValue(next), [])
  return [value, update] as const
}
