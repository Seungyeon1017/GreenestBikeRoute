/**
 * Calls to the users endpoints of the backend (backend/users): sign-up, login,
 * the current user and saved routes. Separate from greenestApi.ts (the routing
 * API), so the two can change without getting in each other's way.
 */
import { GREENEST_API_URL, GreenestApiError } from '@/services/greenestApi'
import type { RouteOptions } from '@/types/greenest'
import type {
  SavedRoute,
  SavedRouteInput,
  SavedRouteOptions,
  User,
} from '@/types/users'

/** Turns FastAPI's `detail` (a sentence, or a list for 422) into one readable line. */
function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail.map(d => d?.msg ?? String(d)).join(' ')
  }
  return `Request failed with status ${status}`
}

/** fetch() against the backend, with the login token if there is one. Throws GreenestApiError. */
async function request<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers, ...rest } = init
  let response: Response
  try {
    response = await fetch(`${GREENEST_API_URL}${path}`, {
      ...rest,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    })
  } catch {
    throw new GreenestApiError(
      `The backend at ${GREENEST_API_URL} is not reachable.`,
    )
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new GreenestApiError(
      errorMessage(body?.detail, response.status),
      response.status,
    )
  }
  // 204 No Content (DELETE) has no body.
  return (response.status === 204 ? undefined : response.json()) as Promise<T>
}

/** POST /users: create an account. 409 if the email is taken. */
export function signUp(
  email: string,
  password: string,
  displayName: string,
): Promise<User> {
  return request<User>('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      password,
      display_name: displayName.trim() || null,
    }),
  })
}

/** POST /auth/login: returns the token. It's a form, not JSON, with the email as `username`. */
export async function logIn(email: string, password: string): Promise<string> {
  const body = await request<{ access_token: string }>('/auth/login', {
    method: 'POST',
    body: new URLSearchParams({ username: email, password }),
  })
  return body.access_token
}

/** GET /users/me: who the token belongs to. 401 if it's invalid or expired. */
export function fetchMe(token: string): Promise<User> {
  return request<User>('/users/me', { token })
}

/** GET /users/me/routes: newest first (the backend keeps the newest 3). */
export function fetchSavedRoutes(token: string): Promise<SavedRoute[]> {
  return request<SavedRoute[]>('/users/me/routes', { token })
}

/** POST /users/me/routes. Saving one more than the backend keeps drops the oldest. */
export function saveRoute(
  token: string,
  route: SavedRouteInput,
): Promise<SavedRoute> {
  return request<SavedRoute>('/users/me/routes', {
    method: 'POST',
    token,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(route),
  })
}

/** DELETE /users/me/routes/{id}. */
export function deleteSavedRoute(token: string, id: number): Promise<void> {
  return request<void>(`/users/me/routes/${id}`, { method: 'DELETE', token })
}

/** The Plan a Trip options in the names the backend stores (same as /route/compare). */
export function toSavedOptions(options: RouteOptions): SavedRouteOptions {
  return {
    bump_penalty: options.bump,
    danger_penalty: options.danger,
    pm_penalty: options.pm,
    stop_penalty: options.stop,
    prefer_bike_friendly: options.bikeFriendly,
    prefer_time: options.preferTime,
    shade_penalty: options.shade,
    dark_penalty: options.dark,
    depart_time: options.departTime || null,
  }
}

/** The reverse of toSavedOptions, to put a saved route's options back into the form. */
export function fromSavedOptions(saved: SavedRouteOptions): RouteOptions {
  return {
    bump: saved.bump_penalty,
    danger: saved.danger_penalty,
    pm: saved.pm_penalty,
    stop: saved.stop_penalty,
    bikeFriendly: saved.prefer_bike_friendly,
    preferTime: saved.prefer_time,
    shade: saved.shade_penalty,
    dark: saved.dark_penalty,
    departTime: saved.depart_time ?? '',
  }
}
