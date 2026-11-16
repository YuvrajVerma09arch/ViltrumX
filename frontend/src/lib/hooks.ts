/**
 * Data-fetching hooks.
 *
 * `useApi` is the workhorse: it runs a fetcher and returns
 * `{ data, loading, error, live }`. Callers pass an *honest empty default*
 * (`[]`, `0`, `—`, …) as `fallback`: if the request fails, the screen renders
 * an empty state rather than another tenant's numbers. Never pass a value
 * from `data/mock.ts` as a fallback — that would show the PayKraft demo
 * fixtures to a real customer with no data. The returned `live` flag is true
 * only when the data actually came from the API, so the UI can label its
 * source accurately.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { streamUrl } from './api'

export type ApiState<T> = {
  data: T
  loading: boolean
  error: string | null
  /** true = served by the API; false = showing the caller's empty fallback (request failed) */
  live: boolean
  reload: () => void
}

export function useApi<T>(
  fetcher: () => Promise<unknown>,
  fallback: T,
  deps: unknown[] = [],
): ApiState<T> {
  const [data, setData] = useState<T>(fallback)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(false)
  const [nonce, setNonce] = useState(0)

  // Keep the latest fetcher without making it a dependency — callers pass
  // inline arrows, which would otherwise re-run the effect on every render.
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    fetcherRef
      .current()
      .then((result) => {
        if (cancelled) return
        setData(result as T)
        setLive(true)
        setError(null)
      })
      .catch((err: Error) => {
        if (cancelled) return
        setData(fallback)
        setLive(false)
        setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, ...deps])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, loading, error, live, reload }
}

/* ── live activity stream (Command Deck) ─────────────────────────────── */

export type FeedLine = {
  t: string
  agent: string
  line: string
  tone: string
}

/**
 * Subscribe to the Django Channels stream. New lines are prepended to
 * `seed`. If the socket can't connect the seed list just stays put — the
 * Command Deck still renders, it simply doesn't tick.
 */
export function useLiveFeed(seed: FeedLine[]) {
  const [lines, setLines] = useState<FeedLine[]>(seed)
  const [connected, setConnected] = useState(false)

  useEffect(() => setLines(seed), [seed])

  useEffect(() => {
    let socket: WebSocket | null = null
    let closed = false

    try {
      socket = new WebSocket(streamUrl())
    } catch {
      return
    }

    socket.onopen = () => !closed && setConnected(true)
    socket.onclose = () => !closed && setConnected(false)
    socket.onerror = () => !closed && setConnected(false)
    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as Partial<FeedLine>
        if (!msg.line) return
        setLines((prev) =>
          [
            {
              t: msg.t ?? '',
              agent: msg.agent ?? 'Agent',
              line: msg.line as string,
              tone: msg.tone ?? 'info',
            },
            ...prev,
          ].slice(0, 60),
        )
      } catch {
        /* ignore malformed frames */
      }
    }

    return () => {
      closed = true
      socket?.close()
    }
  }, [])

  return { lines, connected }
}
