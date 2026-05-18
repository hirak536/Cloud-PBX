import { useEffect, useRef, useState } from 'react'
import { Play, Pause, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

function formatDuration(secs) {
  if (!secs) return '0:00'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

/**
 * AudioPlayer
 * Props:
 *   fetchAudio  - async () => { data: Blob }
 *   onPlay      - optional callback when playback starts
 *
 * Before playback: just a play button (sits inline, e.g. next to edit/delete).
 * After first play: play/pause button + progress bar + time.
 */
export default function AudioPlayer({ fetchAudio, onPlay }) {
  const audioRef     = useRef(null)
  const objectUrlRef = useRef(null)
  const onPlayRef    = useRef(onPlay)
  const [playing,   setPlaying]   = useState(false)
  const [started,   setStarted]   = useState(false)
  const [progress,  setProgress]  = useState(0)
  const [current,   setCurrent]   = useState(0)
  const [duration,  setDuration]  = useState(0)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState(false)

  useEffect(() => { onPlayRef.current = onPlay }, [onPlay])

  useEffect(() => () => {
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
  }, [])

  const toggle = async () => {
    const audio = audioRef.current
    if (!audio) return
    if (playing) { audio.pause(); return }
    if (audio.src && audio.src !== window.location.href) { await audio.play(); return }

    setLoading(true); setError(false)
    try {
      const { data } = await fetchAudio()
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = URL.createObjectURL(data)
      audio.src = objectUrlRef.current
      await audio.play()
      setStarted(true)
      onPlayRef.current?.()
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  const seek = (e) => {
    const audio = audioRef.current
    if (!audio || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    audio.currentTime = ((e.clientX - rect.left) / rect.width) * duration
  }

  const btn = (
    <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={toggle} disabled={loading}>
      {loading
        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
        : playing
          ? <Pause className="h-3.5 w-3.5" />
          : <Play  className="h-3.5 w-3.5" />}
    </Button>
  )

  return (
    <>
      <audio
        ref={audioRef}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => { setPlaying(false); setProgress(0); setCurrent(0) }}
        onLoadedMetadata={(e) => setDuration(e.target.duration)}
        onTimeUpdate={(e) => {
          const d = e.target.duration || 1
          setCurrent(e.target.currentTime)
          setProgress(e.target.currentTime / d)
        }}
      />
      {!started
        ? btn
        : (
          <div className="flex items-center gap-2 w-full min-w-[180px]">
            {btn}
            {error
              ? <span className="text-xs text-destructive">Failed to load</span>
              : <>
                  <div
                    className="relative flex-1 h-1.5 rounded-full bg-muted cursor-pointer overflow-hidden"
                    onClick={seek}
                  >
                    <div
                      className="absolute inset-y-0 left-0 rounded-full bg-primary transition-all"
                      style={{ width: `${progress * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground shrink-0 tabular-nums w-16 text-right">
                    {`${formatDuration(Math.round(current))} / ${formatDuration(Math.round(duration))}`}
                  </span>
                </>}
          </div>
        )}
    </>
  )
}
