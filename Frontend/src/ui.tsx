import { useState } from 'react'

// Small presentational helpers (no app logic).

const PATHS: Record<string, string> = {
  studio: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z',
  queue: 'M4 6h16M4 12h16M4 18h10',
  approvals: 'M5 12.5l4.5 4.5L19 7.5',
  history: 'M12 7v5l3 2M4 12a8 8 0 1 0 2.3-5.7M4 5v4h4',
  insights: 'M5 19V11M12 19V5M19 19v-6',
  guidelines: 'M6 4h9l3 3v13H6V4zM9 12h6M9 16h6',
  panel: 'M4 5h16v14H4V5zM9 5v14',
  lock: 'M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6v-9z',
  copy: 'M9 9h10v11H9V9zM5 15V4h10',
  refresh: 'M20 12a8 8 0 1 1-2.5-5.8M20 4v5h-5',
  send: 'M12 19V5M6 11l6-6 6 6',
  plus: 'M12 5v14M5 12h14',
  check: 'M5 12.5l4.5 4.5L19 7.5',
}

export function Icon({ name, className = 'h-5 w-5' }: { name: keyof typeof PATHS | string; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}

/**
 * ENGANO's assistant. While `thinking` it plays the looping thinking animation (transparent
 * WebM); otherwise it shows a still frame. Browsers that can't play VP9-with-alpha fall back
 * to the still frame too.
 */
export function Mascot({ thinking = false, width = 104 }: { thinking?: boolean; width?: number }) {
  const [videoFailed, setVideoFailed] = useState(false)
  const height = Math.round((width * 432) / 544)
  return (
    <div className="shrink-0" style={{ width, height }}>
      {thinking && !videoFailed ? (
        <video
          src="/perry-thinking.webm"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          width={width}
          height={height}
          onError={() => setVideoFailed(true)}
          aria-hidden="true"
        />
      ) : (
        <img src="/perry-still.png" width={width} height={height} alt="" aria-hidden="true" />
      )}
    </div>
  )
}
