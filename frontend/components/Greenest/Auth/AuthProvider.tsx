'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  logIn as apiLogIn,
  signUp as apiSignUp,
  fetchMe,
} from '@/services/usersApi'
import type { User } from '@/types/users'

/** Where the login token is kept in the browser between visits. */
const TOKEN_KEY = 'greenest.token'

type AuthState = {
  /** 'loading' until a stored token has been checked, so pages don't flash "logged out". */
  status: 'loading' | 'anonymous' | 'authenticated'
  user: User | null
  token: string | null
  logIn: (_email: string, _password: string) => Promise<void>
  signUp: (
    _email: string,
    _password: string,
    _displayName: string,
  ) => Promise<void>
  logOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)

function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    return null // storage blocked, e.g. some private windows
  }
}

function writeToken(token: string | null) {
  try {
    if (token) {
      window.localStorage.setItem(TOKEN_KEY, token)
    } else {
      window.localStorage.removeItem(TOKEN_KEY)
    }
  } catch {
    // Without storage the login still works until the page is reloaded.
  }
}

/**
 * Knows who is logged in, for every page below it (wrapped around the pages in
 * app/(greenest)/layout.tsx). Pages read it with useAuth().
 */
export default function AuthProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [status, setStatus] = useState<AuthState['status']>('loading')
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)

  const logOut = useCallback(() => {
    writeToken(null)
    setToken(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  /** Checks a token with /users/me and, if it's valid, remembers it. */
  const acceptToken = useCallback(async (newToken: string) => {
    const me = await fetchMe(newToken)
    writeToken(newToken)
    setToken(newToken)
    setUser(me)
    setStatus('authenticated')
  }, [])

  // On the first visit of a page: is there a token from an earlier login, and is it still valid?
  useEffect(() => {
    const stored = readToken()
    if (!stored) {
      setStatus('anonymous')
      return
    }
    // Expired or invalid (e.g. after the server's secret changed): just log out.
    acceptToken(stored).catch(logOut)
  }, [acceptToken, logOut])

  const logIn = useCallback(
    async (email: string, password: string) => {
      await acceptToken(await apiLogIn(email, password))
    },
    [acceptToken],
  )

  const signUp = useCallback(
    async (email: string, password: string, displayName: string) => {
      await apiSignUp(email, password, displayName)
      await logIn(email, password)
    },
    [logIn],
  )

  const value = useMemo(
    () => ({ status, user, token, logIn, signUp, logOut }),
    [status, user, token, logIn, signUp, logOut],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/** Who is logged in, plus logIn / signUp / logOut. Only works below <AuthProvider>. */
export function useAuth(): AuthState {
  const auth = useContext(AuthContext)
  if (!auth) {
    throw new Error('useAuth() needs <AuthProvider> around the page')
  }
  return auth
}
