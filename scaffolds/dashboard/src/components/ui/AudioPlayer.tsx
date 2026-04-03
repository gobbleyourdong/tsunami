import { useState, useRef, useEffect, useCallback } from "react"

interface Track {
  title: string
  artist?: string
  src: string
  duration?: number
}

interface AudioPlayerProps {
  tracks: Track[]
  autoPlay?: boolean
  onTrackChange?: (index: number) => void
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, "0")}`
}

export default function AudioPlayer({ tracks, autoPlay = false, onTrackChange }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [playing, setPlaying] = useState(false)
  const [currentTrack, setCurrentTrack] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolume] = useState(0.8)

  const track = tracks[currentTrack]

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return
    const onTime = () => setCurrentTime(audio.currentTime)
    const onDur = () => setDuration(audio.duration || 0)
    const onEnd = () => { if (currentTrack < tracks.length - 1) changeTrack(currentTrack + 1); else setPlaying(false) }
    audio.addEventListener("timeupdate", onTime)
    audio.addEventListener("loadedmetadata", onDur)
    audio.addEventListener("ended", onEnd)
    return () => {
      audio.removeEventListener("timeupdate", onTime)
      audio.removeEventListener("loadedmetadata", onDur)
      audio.removeEventListener("ended", onEnd)
    }
  }, [currentTrack, tracks.length])

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume
  }, [volume])

  const togglePlay = useCallback(() => {
    if (!audioRef.current) return
    if (playing) audioRef.current.pause()
    else audioRef.current.play()
    setPlaying(!playing)
  }, [playing])

  const changeTrack = useCallback((idx: number) => {
    setCurrentTrack(idx)
    setCurrentTime(0)
    onTrackChange?.(idx)
    setTimeout(() => { if (audioRef.current && (playing || autoPlay)) audioRef.current.play() }, 50)
  }, [playing, autoPlay, onTrackChange])

  const seek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    audioRef.current.currentTime = pct * duration
  }, [duration])

  const progress = duration ? (currentTime / duration) * 100 : 0

  return (
    <div style={{
      background: "var(--bg-secondary, #111827)",
      border: "1px solid var(--border, rgba(255,255,255,0.08))",
      borderRadius: "var(--radius-md, 8px)", overflow: "hidden",
    }}>
      <audio ref={audioRef} src={track?.src} preload="metadata" />

      {/* Now playing */}
      <div style={{ padding: "16px 16px 12px" }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary, #e2e8f0)" }}>
          {track?.title || "No track"}
        </div>
        {track?.artist && (
          <div style={{ fontSize: 13, color: "var(--text-secondary, #94a3b8)", marginTop: 2 }}>
            {track.artist}
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div
        onClick={seek}
        style={{
          height: 4, background: "var(--bg-tertiary, #1a2332)",
          cursor: "pointer", margin: "0 16px",
          borderRadius: 2, overflow: "hidden",
        }}
      >
        <div style={{
          height: "100%", width: `${progress}%`,
          background: "var(--accent, #4a9eff)",
          transition: "width 100ms linear",
          borderRadius: 2,
        }} />
      </div>

      {/* Time + controls */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 16px 12px" }}>
        <span style={{ fontSize: 11, color: "var(--text-dim, #4a4f5e)", minWidth: 36 }}>
          {formatTime(currentTime)}
        </span>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <button
            onClick={() => currentTrack > 0 && changeTrack(currentTrack - 1)}
            disabled={currentTrack === 0}
            style={{ background: "none", border: "none", color: "var(--text-secondary, #94a3b8)", cursor: "pointer", fontSize: 16, opacity: currentTrack === 0 ? 0.3 : 1 }}
          >
            ⏮
          </button>
          <button
            onClick={togglePlay}
            style={{
              background: "var(--accent, #4a9eff)", border: "none", color: "#fff",
              width: 36, height: 36, borderRadius: "50%", cursor: "pointer",
              fontSize: 14, display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            {playing ? "⏸" : "▶"}
          </button>
          <button
            onClick={() => currentTrack < tracks.length - 1 && changeTrack(currentTrack + 1)}
            disabled={currentTrack >= tracks.length - 1}
            style={{ background: "none", border: "none", color: "var(--text-secondary, #94a3b8)", cursor: "pointer", fontSize: 16, opacity: currentTrack >= tracks.length - 1 ? 0.3 : 1 }}
          >
            ⏭
          </button>
        </div>
        <span style={{ fontSize: 11, color: "var(--text-dim, #4a4f5e)", minWidth: 36, textAlign: "right" }}>
          {formatTime(duration)}
        </span>
      </div>

      {/* Volume */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 16px 12px" }}>
        <span style={{ fontSize: 12, color: "var(--text-dim, #4a4f5e)" }}>Vol</span>
        <input
          type="range" min={0} max={1} step={0.01} value={volume}
          onChange={e => setVolume(parseFloat(e.target.value))}
          style={{ flex: 1, accentColor: "var(--accent, #4a9eff)" }}
        />
      </div>

      {/* Playlist */}
      {tracks.length > 1 && (
        <div style={{ borderTop: "1px solid var(--border, rgba(255,255,255,0.08))", maxHeight: 200, overflow: "auto" }}>
          {tracks.map((t, i) => (
            <div
              key={i}
              onClick={() => changeTrack(i)}
              style={{
                padding: "8px 16px", cursor: "pointer", fontSize: 13,
                display: "flex", justifyContent: "space-between",
                background: i === currentTrack ? "var(--bg-tertiary, #1a2332)" : "transparent",
                color: i === currentTrack ? "var(--accent, #4a9eff)" : "var(--text-primary, #e2e8f0)",
              }}
            >
              <span>{t.title}</span>
              {t.artist && <span style={{ color: "var(--text-dim, #4a4f5e)" }}>{t.artist}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
