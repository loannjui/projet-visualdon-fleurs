const ALT_MAX = 3786
const ALT_MIN = 300

function AltitudeSlider({ value, onChange }) {
  const pct = 100 - ((value - ALT_MIN) / (ALT_MAX - ALT_MIN)) * 100

  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const y = e.clientY - rect.top
    const t = Math.max(0, Math.min(1, y / rect.height))
    const targetAlt = Math.round(ALT_MAX - t * (ALT_MAX - ALT_MIN))
    onChange?.(targetAlt)
  }

  return (
    <div className="panel panel-altitude">
      <span className="panel-title">Altitude</span>
      <div className="altitude-body">
        <div
          className="altitude-track-area"
          onClick={handleClick}
          style={{ cursor: 'pointer' }}
        >
          <div className="altitude-current-indicator" style={{ top: `${pct}%` }}>
            <span className="altitude-dot" />
            <span className="altitude-current-label">{value}m</span>
          </div>
          <div className="altitude-track-line" />
        </div>
        <div className="altitude-min-mark">
          <span className="altitude-corner">└</span>
          <span className="altitude-min-label">300m</span>
        </div>
      </div>
    </div>
  )
}

export default AltitudeSlider
