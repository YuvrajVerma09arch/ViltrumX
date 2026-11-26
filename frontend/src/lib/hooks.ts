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
import { endpoints, streamUrl } from './api'

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

/** How the feed is actually being sourced right now, so the UI can say so. */
export type FeedMode = 'live' | 'polling' | 'offline'

export type LiveFeed = {
  lines: FeedLine[]
  connected: boolean
  mode: FeedMode
}

const FEED_POLL_MS = 5000

/**
 * Subscribe to the Django Channels stream, falling back to polling
 * `/feed` every 5s when there is no tenant (no socket URL) or the socket
 * closes. New lines are prepended to `seed`. `mode` reports which path is
 * active: 'live' (socket open), 'polling' (REST fallback), or 'offline'
 * (no socket and the last poll failed). Polling pauses while the tab is
 * hidden; all timers/sockets are torn down on unmount.
 */
export function useLiveFeed(seed: FeedLine[]): LiveFeed {
  const [lines, setLines] = useState<FeedLine[]>(seed)
  const [connected, setConnected] = useState(false)
  const [mode, setMode] = useState<FeedMode>('offline')

  useEffect(() => setLines(seed), [seed])

  useEffect(() => {
    let socket: WebSocket | null = null
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let closed = false

    function keyOf(row: Partial<FeedLine>): string {
      return `${row.t ?? ''}|${row.agent ?? ''}|${row.line ?? ''}`
    }

    // Prepend a row unless an identical line is already on screen — this
    // keeps re-polling the full feed (or the seed overlapping the first poll)
    // from stacking duplicate copies.
    function prepend(row: Partial<FeedLine>) {
      if (!row.line) return
      const key = keyOf(row)
      setLines((prev) => {
        if (prev.some((p) => keyOf(p) === key)) return prev
        return [
          {
            t: row.t ?? '',
            agent: row.agent ?? 'Agent',
            line: row.line as string,
            tone: row.tone ?? 'info',
          },
          ...prev,
        ].slice(0, 60)
      })
    }

    // REST fallback: poll the feed and prepend only rows we don't yet show.
    // `endpoints.feed()` returns newest-first, so reverse to preserve order
    // as each row is prepended.
    async function poll() {
      if (document.hidden) return
      try {
        const rows = (await endpoints.feed()) as Partial<FeedLine>[]
        if (closed) return
        setMode('polling')
        rows.slice().reverse().forEach(prepend)
      } catch {
        if (!closed) setMode('offline')
      }
    }

    function startPolling() {
      if (pollTimer || closed) return
      setMode('polling')
      void poll()
      pollTimer = setInterval(poll, FEED_POLL_MS)
    }

    function stopPolling() {
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }

    const url = streamUrl()
    if (!url) {
      // No tenant yet — poll until (if ever) a tenant appears on reload.
      startPolling()
      return () => {
        closed = true
        stopPolling()
      }
    }

    try {
      socket = new WebSocket(url)
    } catch {
      startPolling()
      return () => {
        closed = true
        stopPolling()
      }
    }

    socket.onopen = () => {
      if (closed) return
      setConnected(true)
      setMode('live')
      stopPolling()
    }
    socket.onclose = () => {
      if (closed) return
      setConnected(false)
      startPolling()
    }
    socket.onerror = () => {
      if (closed) return
      setConnected(false)
    }
    socket.onmessage = (event) => {
      try {
        prepend(JSON.parse(event.data) as Partial<FeedLine>)
      } catch {
        /* ignore malformed frames */
      }
    }

    return () => {
      closed = true
      stopPolling()
      socket?.close()
    }
  }, [])

  return { lines, connected, mode }
}
