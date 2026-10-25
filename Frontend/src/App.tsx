import { auth, type Me } from './appApi'
import Dashboard from './Dashboard'
import SignIn from './pages/SignIn'
import { usePersisted } from './storage'

export type Finding = {
  severity: 'Critical' | 'Warning' | 'Suggestion'
  category: string
  issue: string
  explanation: string
  guideline: string
  suggestion: string
  // Set for findings that can be underlined and fixed inside the editor.
  quote?: string
  start?: number
  replacement?: string
  append?: string
  // Set when the finding is about an attached image (1-based).
  imageIndex?: number
  suggestedAlt?: string
}

export type Guideline = {
  id: number
  type: 'DO' | "DON'T"
  text: string
}

type Login = { token: string; me: Me }

/** Sign in or sign up, then the dashboard for that account's role. The login belongs to this tab. */
function App() {
  const [login, setLogin] = usePersisted<Login | null>('engano_login', null, 'session')

  if (!login) return <SignIn onSignedIn={(token, me) => setLogin({ token, me })} />

  const leave = () => {
    void auth.signOut(login.token)
    setLogin(null)
  }
  return <Dashboard key={login.me.id} token={login.token} onLogout={leave} />
}

export default App
