import gsap from 'gsap'

const BASE_COLOR = '#fffbe8'

// Assignations par couche : prefix -> { shapeId -> flower }
const shapeAssignments = { montagne: {}, plaine: {}, ville: {} }

function assignRandomGSAP(flowers, prefix, count, shapeToFlower) {
  const assignments = shapeAssignments[prefix]

  // Garder les formes dont la fleur est toujours valide, libérer les autres
  const freeIndices = []
  for (let i = 1; i <= count; i++) {
    const id = `${prefix}-${i}`
    const existing = assignments[id]
    if (existing && flowers.includes(existing)) {
      shapeToFlower[id] = existing
    } else {
      if (existing) {
        delete assignments[id]
        document.getElementById(id)?.classList.remove('shape--colored')
      }
      freeIndices.push(i)
    }
  }

  // Exclure les fleurs déjà utilisées dans cette couche seulement
  const usedFlowers = new Set(Object.values(assignments))
  const available = flowers.filter(f => !usedFlowers.has(f)).sort(() => Math.random() - 0.5)

  freeIndices.forEach((i, idx) => {
    const id = `${prefix}-${i}`
    const el = document.getElementById(id)
    if (!el) return

    const flower = available[idx] ?? null
    const fillColor = flower ? flower.couleur : BASE_COLOR

    gsap.to(el, {
      fill: fillColor,
      duration: 0.8,
      delay: idx * 0.04,
      ease: 'power2.inOut',
    })

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
