/**
 * Riders' leisure routes (backend/users/community_routes.py): recorded rides
 * uploaded as GPX, which everyone can browse, heart, save and flag.
 */
import { request } from '@/services/usersApi'
import type {
  CommunityRoute,
  CommunityRouteInput,
  CommunityRouteList,
  CommunityRouteSort,
  CommunityRouteSummary,
  RouteTag,
  TrackPreview,
} from '@/types/users'

/** POST /community-routes/preview: checks the file and returns the ride as it would be published. */
export function previewTrack(token: string, file: File): Promise<TrackPreview> {
  const body = new FormData()
  body.append('file', file)
  return request<TrackPreview>('/community-routes/preview', {
    method: 'POST',
    token,
    body,
  })
}

/** POST /community-routes: publishes the ride for everyone. */
export function publishRoute(
  token: string,
  file: File,
  input: CommunityRouteInput,
): Promise<CommunityRoute> {
  const body = new FormData()
  body.append('file', file)
  body.append('name', input.name)
  body.append('description', input.description)
  input.tags.forEach(tag => body.append('tags', tag))
  return request<CommunityRoute>('/community-routes', {
    method: 'POST',
    token,
    body,
  })
}

/** GET /community-routes: published routes; with a token each says whether you hearted or saved it. */
export function fetchCommunityRoutes(
  token: string | null,
  {
    sort,
    tag,
    limit,
    offset,
  }: {
    sort: CommunityRouteSort
    tag: RouteTag | null
    limit: number
    offset: number
  },
): Promise<CommunityRouteList> {
  const query = new URLSearchParams({
    sort,
    limit: String(limit),
    offset: String(offset),
  })
  if (tag) {
    query.set('tag', tag)
  }
  return request<CommunityRouteList>(`/community-routes?${query}`, { token })
}

/** GET /community-routes/{id}: one route with its whole line. */
export function fetchCommunityRoute(
  token: string | null,
  id: number,
): Promise<CommunityRoute> {
  return request<CommunityRoute>(`/community-routes/${id}`, { token })
}

/** DELETE /community-routes/{id}: only your own. */
export function deleteCommunityRoute(token: string, id: number): Promise<void> {
  return request<void>(`/community-routes/${id}`, { method: 'DELETE', token })
}

/** PUT or DELETE /community-routes/{id}/heart. */
export function setHeart(
  token: string,
  id: number,
  hearted: boolean,
): Promise<{ hearts: number; hearted: boolean }> {
  return request(`/community-routes/${id}/heart`, {
    method: hearted ? 'PUT' : 'DELETE',
    token,
  })
}

/** PUT or DELETE /community-routes/{id}/save. */
export function setSaved(
  token: string,
  id: number,
  saved: boolean,
): Promise<void> {
  return request<void>(`/community-routes/${id}/save`, {
    method: saved ? 'PUT' : 'DELETE',
    token,
  })
}

/** POST /community-routes/{id}/flag: enough flags hide the route until a maintainer checks it. */
export function flagRoute(
  token: string,
  id: number,
  reason: string,
): Promise<void> {
  return request<void>(`/community-routes/${id}/flag`, {
    method: 'POST',
    token,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason.trim() || null }),
  })
}

/** GET /users/me/community-routes: the routes you published, whatever their status. */
export function fetchMyCommunityRoutes(
  token: string,
): Promise<CommunityRouteSummary[]> {
  return request<CommunityRouteSummary[]>('/users/me/community-routes', {
    token,
  })
}

/** GET /users/me/community-routes/saved. */
export function fetchSavedCommunityRoutes(
  token: string,
): Promise<CommunityRouteSummary[]> {
  return request<CommunityRouteSummary[]>('/users/me/community-routes/saved', {
    token,
  })
}
