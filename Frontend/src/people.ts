import { createContext, useContext } from 'react'

/** Account id -> the name people see. Ids are generated and never shown. */
export const PeopleContext = createContext<Record<string, string>>({})

export function useNameOf() {
  const names = useContext(PeopleContext)
  return (id: string) => names[id] ?? 'Unknown user'
}
