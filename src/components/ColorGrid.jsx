import { useMemo } from 'react'
import fleursData from '../data/fleurs'

const ALT_MIN = 0
const ALT_MAX = 3500
const COLS = 36 // 3 squares per month × 12 months

function topColors(flowers, n = 2) {
  if (flowers.length === 0) return ['#1a1a1a']
  const counts = {}
  flowers.forEach(f => {
    counts[f.couleur] = (counts[f.couleur] || 0) + f.nb_occurrences
  })
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([color]) => color)
}

function ColorGrid({ mode, fading }) {
  const squares = useMemo(() => {
    const cols = COLS
    const squarePx = window.innerWidth / COLS
    const rows = Math.ceil(window.innerHeight / squarePx) + 1
    const total = cols * rows

    if (mode === 'random') {
      const colors = fleursData.map(f => f.couleur)
      return {
        cols,
        items: Array.from({ length: total }, (_, i) => ({
          id: i,
          color: colors[Math.floor(Math.random() * colors.length)],
          delay: Math.random() * 0.8,
        })),
      }
    }

    // mode === 'data': X = mois, Y = altitude
    const colsPerMonth = cols / 12
    const colorMap = {}
    for (let row = 0; row < rows; row++) {
      const altBandMax = ALT_MAX - (row / rows) * (ALT_MAX - ALT_MIN)
      const altBandMin = ALT_MAX - ((row + 1) / rows) * (ALT_MAX - ALT_MIN)
      for (let month = 1; month <= 12; month++) {
        const matching = fleursData.filter(f =>
          f.mois_floraison.includes(month) &&
          f.altitude.max >= altBandMin &&
          f.altitude.min <= altBandMax
        )
        colorMap[`${month}-${row}`] = topColors(matching, 4)
      }
    }

    const items = []
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const month = Math.min(Math.floor(col / colsPerMonth) + 1, 12)
        const monthStartCol = Math.floor((month - 1) * colsPerMonth)
        const posInMonth = col - monthStartCol
        const palette = colorMap[`${month}-${row}`]
        items.push({
          id: row * cols + col,
          color: palette[posInMonth % palette.length],
          delay: Math.random() * 0.8,
        })
      }
    }

    return { cols, items }
  }, [mode])

  return (
    <div className={`color-grid${fading ? ' color-grid--fading' : ''}`} style={{ '--cols': squares.cols }}>
      {squares.items.map(sq => (
        <div
          key={sq.id}
          className="color-square"
          style={{
            backgroundColor: sq.color,
            animationDelay: `${sq.delay}s`,
          }}
        />
      ))}
    </div>
  )
}

export default ColorGrid
