import { useState, useRef, useEffect, useCallback } from "react"

interface VideoPlayerProps {
  src: string
  poster?: string
  autoPlay?: boolean
  loop?: boolean
  subtitles?: { src: string; label: string; lang: string }[]
  onTimeUpdate?: (time: number) => void
}

function formatTime(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`
  return `${m}:${sec.toString().padStart(2, "0")}`
}

export default function VideoPlayer({ src, poster, autoPlay = false, loop = false, subtitles = [], onTimeUpdate }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(1)
  const [muted, setMuted] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const [showControls, setShowControls] = useState(true)
  const hideTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    const onTime = () => { setCurrentTime(v.currentTime); onTimeUpdate?.(v.currentTime) }
    const onDur = () => setDuration(v.duration || 0)
    const onPlay = () => setPlaying(true)
    const onPause = () => setPlaying(false)
    v.addEventListener("timeupdate", onTime)
    v.addEventListener("loadedmetadata", onDur)
    v.addEventListener("play", onPlay)
    v.addEventListener("pause", onPause)
    return () => { v.removeEventListener("timeupdate", onTime); v.removeEventListener("loadedmetadata", onDur); v.removeEventListener("play", onPlay); v.removeEventListener("pause", onPause) }
  }, [onTimeUpdate])

  useEffect(() => { if (videoRef.current) { videoRef.current.volume = volume; videoRef.current.muted = muted } }, [volume, muted])

  const togglePlay = useCallback(() => {
    if (!videoRef.current) return
    if (playing) videoRef.current.pause()
    else videoRef.current.play()
  }, [playing])

  const seek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    videoRef.current.currentTime = ((e.clientX - rect.left) / rect.width) * duration
  }, [duration])

  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen()
      setFullscreen(true)
    } else {
      document.exitFullscreen()
      setFullscreen(false)
    }
  }, [])

  const togglePiP = useCallback(async () => {
    if (!videoRef.current) return
    try {
      if (document.pictureInPictureElement) await document.exitPictureInPicture()
      else await videoRef.current.requestPictureInPicture()
    } catch { /* PiP not supported */ }
  }, [])

  const handleMouseMove = () => {
    setShowControls(true)
    clearTimeout(hideTimer.current)
    hideTimer.current = setTimeout(() => { if (playing) setShowControls(false) }, 3000)
  }

  const progress = duration ? (currentTime / duration) * 100 : 0

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => { if (playing) setShowControls(false) }}
      style={{
        position: "relative", background: "#000",
        borderRadius: fullscreen ? 0 : "var(--radius-md, 8px)",
        overflow: "hidden", cursor: showControls ? "default" : "none",
      }}
    >
      <video
        ref={videoRef}
        src={src}
        poster={poster}
        autoPlay={autoPlay}
        loop={loop}
        onClick={togglePlay}
        style={{ width: "100%", display: "block" }}
      >
        {subtitles.map((sub, i) => (
          <track key={i} kind="subtitles" src={sub.src} srcLang={sub.lang} label={sub.label} />
        ))}
      </video>

      {/* Controls overlay */}
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0,
        background: "linear-gradient(transparent, rgba(0,0,0,0.8))",
        padding: "24px 12px 8px",
        opacity: showControls ? 1 : 0,
        transition: "opacity 300ms",
      }}>
        {/* Progress */}
        <div onClick={seek} style={{
          height: 4, background: "rgba(255,255,255,0.2)", cursor: "pointer",
          borderRadius: 2, marginBottom: 8,
        }}>
          <div style={{ height: "100%", width: `${progress}%`, background: "var(--accent, #4a9eff)", borderRadius: 2 }} />
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button onClick={togglePlay} style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", fontSize: 16 }}>
              {playing ? "⏸" : "▶"}
            </button>
            <button onClick={() => setMuted(!muted)} style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", fontSize: 14 }}>
              {muted ? "🔇" : "🔊"}
            </button>
            <input type="range" min={0} max={1} step={0.05} value={muted ? 0 : volume}
              onChange={e => { setVolume(parseFloat(e.target.value)); setMuted(false) }}
              style={{ width: 60, accentColor: "var(--accent, #4a9eff)" }}
            />
            <span style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={togglePiP} title="Picture-in-Picture"
              style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", fontSize: 14 }}>
              PiP
            </button>
            <button onClick={toggleFullscreen}
              style={{ background: "none", border: "none", color: "#fff", cursor: "pointer", fontSize: 14 }}>
              {fullscreen ? "⊡" : "⛶"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
