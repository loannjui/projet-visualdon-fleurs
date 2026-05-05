import gsap from 'gsap'

const BASE_COLOR = '#fffbe8'

// Persistent assignments per layer: prefix -> { shapeId -> flower }
const shapeAssignments = { montagne: {}, plaine: {}, ville: {} }

function assignRandomGSAP(flowers, prefix, count, shapeToFlower) {
  const assignments = shapeAssignments[prefix]
  const freeIndices = []
  const keptColors = new Set()

  // Keep valid shapes whose color hasn't been claimed yet; free everything else
  for (let i = 1; i <= count; i++) {
    const id = `${prefix}-${i}`
    const existing = assignments[id]
    if (existing && flowers.includes(existing) && !keptColors.has(existing.couleur)) {
      keptColors.add(existing.couleur)
      shapeToFlower[id] = existing
    } else {
      if (existing) {
        delete assignments[id]
        document.getElementById(id)?.classList.remove('shape--colored')
      }
      freeIndices.push(i)
    }
  }

  // One flower per unique color, excluding colors already held by kept shapes
  const seenColors = new Set(keptColors)
  const available = []
  for (const f of flowers.slice().sort(() => Math.random() - 0.5)) {
    if (!seenColors.has(f.couleur)) {
      seenColors.add(f.couleur)
      available.push(f)
    }
  }

  freeIndices.forEach((i, idx) => {
    const id = `${prefix}-${i}`
    const el = document.getElementById(id)
    if (!el) return

    const flower = available[idx] ?? null
    const fillColor = flower ? flower.couleur : BASE_COLOR

    // No stagger delay — avoids the window where a shape is clickable but still shows BASE_COLOR
    gsap.to(el, { fill: fillColor, duration: 0.8, ease: 'power2.inOut' })

    if (flower) {
      assignments[id] = flower
      shapeToFlower[id] = flower
      el.classList.add('shape--colored')
    } else {
      el.classList.remove('shape--colored')
    }
  })
}

export function updateAllLayers(flowers) {
  const montFlowers   = flowers.filter(f => f.altitude.max >= 1500)
  const plaineFlowers = flowers.filter(f => f.altitude.min <= 1500 && f.altitude.max >= 300)
  const villeFlowers  = flowers.filter(f => f.altitude.min <= 600)

  const shapeToFlower = {}

  assignRandomGSAP(montFlowers,   'montagne', 20, shapeToFlower)
  assignRandomGSAP(plaineFlowers, 'plaine',   35, shapeToFlower)
  assignRandomGSAP(villeFlowers,  'ville',    31, shapeToFlower)

  return shapeToFlower
}
