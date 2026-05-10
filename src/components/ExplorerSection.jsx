import { useState, useEffect, useRef, useMemo } from 'react'
import { useFlowerFilter } from '../hooks/useFlowerFilter'
import { updateAllLayers } from '../utils/updateSVGColors'
import MonthSlider from './MonthSlider.jsx'
import AltitudeSlider from './AltitudeSlider.jsx'
import ExportButton from './ExportButton.jsx'
import FlowerModal from './FlowerModal.jsx'
import MontagneIllustration from '../illustrations/montagne.svg?react'
import PlaineIllustration from '../illustrations/plaine.svg?react'
import VilleIllustration from '../illustrations/ville.svg?react'

function ExplorerSection({ onHome }) {
  const [altitude, setAltitude] = useState(3786)
  const [month, setMonth] = useState(6)
  const [selectedFlowers, setSelectedFlowers] = useState([])
  const [shapeToFlower, setShapeToFlower] = useState({})

  const montRef    = useRef(null)
  const plaineRef  = useRef(null)
  const villeRef   = useRef(null)
  const flowersRef  = useRef([])
  const altitudeRef = useRef(altitude)

  const { flowers } = useFlowerFilter(altitude, month)

  useEffect(() => { flowersRef.current  = flowers  }, [flowers])
  useEffect(() => { altitudeRef.current = altitude }, [altitude])

  const prevFlowerKeyRef = useRef('')

  useEffect(() => {
    const zone = altitude > 2200 ? 'mont' : altitude > 850 ? 'plaine' : 'ville'
    const key = zone + '|' + flowers.map(f => f.nom).join(',')
    if (key === prevFlowerKeyRef.current) return
    prevFlowerKeyRef.current = key
    const mapping = updateAllLayers(flowers, altitudeRef.current)
    setShapeToFlower(mapping)
  }, [flowers, altitude])

  const swatchAltitude = Math.round(altitude / 300) * 300
  const displayedColors = useMemo(() => {
    const seen = new Set()
    const byCenter = []
    for (const f of [...flowers].sort((a, b) =>
      (a.altitude.min + a.altitude.max) - (b.altitude.min + b.altitude.max)
    )) {
      if (!seen.has(f.couleur)) { seen.add(f.couleur); byCenter.push(f.couleur) }
    }
    const t = (swatchAltitude - 300) / (3786 - 300)
    const startIdx = Math.floor(t * Math.max(0, byCenter.length - 12))
    return byCenter.slice(startIdx, startIdx + 12).sort()
  }, [flowers, swatchAltitude])

  const swatchRows = Math.max(1, Math.ceil(displayedColors.length / 6))
  const swatchMaxH = swatchRows * 52 + (swatchRows - 1) * 10 + 10 + 12

  useEffect(() => {
    const cleanup = []
    Object.entries(shapeToFlower).forEach(([id, flower]) => {
      const el = document.getElementById(id)
      if (!el) return
      const handler = () => {
        const siblings = flowersRef.current.filter(f => f.couleur === flower.couleur)
        setSelectedFlowers(siblings.length > 0 ? siblings : [flower])
      }
      el.addEventListener('click', handler)
      el.style.cursor = 'pointer'
      cleanup.push(() => { el.removeEventListener('click', handler); el.style.cursor = '' })
    })
    return () => cleanup.forEach(fn => fn())
  }, [shapeToFlower])

  // Altitude driven by scroll position mapped to section boundaries
  useEffect(() => {
    const onScroll = () => {
      const mont   = montRef.current
      const plaine = plaineRef.current
      const ville  = villeRef.current
      if (!mont || !plaine || !ville) return

      const scrollTop = window.scrollY
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight

      // Absolute top of each section in document coordinates
      const montTop   = mont.getBoundingClientRect().top   + scrollTop
      const plaineTop = plaine.getBoundingClientRect().top + scrollTop
      const villeTop  = ville.getBoundingClientRect().top  + scrollTop

      let newAlt
      if (scrollTop < plaineTop) {
        // montagne zone → 3786 down to 1500
        const p = Math.max(0, scrollTop - montTop) / (plaineTop - montTop)
        newAlt = 3786 - Math.min(1, p) * (3786 - 1500)
      } else if (scrollTop < villeTop) {
        // plaine zone → 1500 down to 600
        const p = (scrollTop - plaineTop) / (villeTop - plaineTop)
        newAlt = 1500 - Math.min(1, p) * (1500 - 600)
      } else {
        // ville zone → 600 down to 300 (ends at 300 when fully scrolled)
        const remaining = Math.max(1, maxScroll - villeTop)
        const p = (scrollTop - villeTop) / remaining
        newAlt = 600 - Math.min(1, p) * (600 - 300)
      }

      setAltitude(Math.min(3786, Math.max(300, Math.round(newAlt))))
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const seekToAltitude = (targetAlt) => {
    const mont   = montRef.current
    const plaine = plaineRef.current
    const ville  = villeRef.current
    if (!mont || !plaine || !ville) return

    const scrollTop = window.scrollY
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight
    const montTop   = mont.getBoundingClientRect().top   + scrollTop
    const plaineTop = plaine.getBoundingClientRect().top + scrollTop
    const villeTop  = ville.getBoundingClientRect().top  + scrollTop

    let target
    if (targetAlt >= 1500) {
      const p = (3786 - targetAlt) / (3786 - 1500)
      target = montTop + p * (plaineTop - montTop)
    } else if (targetAlt >= 600) {
      const p = (1500 - targetAlt) / (1500 - 600)
      target = plaineTop + p * (villeTop - plaineTop)
    } else {
      const p = (600 - targetAlt) / (600 - 300)
      const remaining = Math.max(1, maxScroll - villeTop)
      target = villeTop + p * remaining
    }

    window.lenis?.scrollTo(Math.round(target))
  }

  return (
    <section className="explorer-section">

      {/* Panneaux de contrôle — fixes sur l'écran pendant tout le scroll */}
      <div className="controls-overlay">
        <button className="home-btn" onClick={onHome} aria-label="Retour à l'accueil">
          ← Accueil
        </button>

        <div className="panel panel-dominant">
          <div className="panel-dominant-header">
            <span className="panel-title">Couleurs dominantes</span>
            <ExportButton targetId="dominant-export-target" colors={displayedColors} />
          </div>
          <div
            className="dominant-swatches"
            id="dominant-export-target"
            style={{ maxHeight: swatchMaxH }}
          >
            {displayedColors.map(color => (
              <div
                key={color}
                className="dominant-swatch"
                style={{ backgroundColor: color, cursor: 'pointer' }}
                onClick={() => {
                  setSelectedFlowers(flowersRef.current.filter(f => f.couleur === color))
                }}
              />
            ))}
          </div>
        </div>

        <AltitudeSlider value={altitude} onChange={seekToAltitude} />
        <MonthSlider value={month} onChange={setMonth} />
      </div>

      {/* Les 3 SVGs empilés — scroll naturel à travers chacun */}
      <div className="layer-wrap layer-montagne" ref={montRef}>
        <div className="svg-sticky">
          <MontagneIllustration className="svg-layer" />
        </div>
      </div>
      <div className="layer-wrap layer-plaine" ref={plaineRef}>
        <div className="svg-sticky">
          <PlaineIllustration className="svg-layer" />
        </div>
      </div>
      <div className="layer-wrap layer-ville" ref={villeRef}>
        <div className="svg-sticky">
          <VilleIllustration className="svg-layer" />
        </div>
      </div>

      <FlowerModal flowers={selectedFlowers} onClose={() => setSelectedFlowers([])} />
    </section>
  )
}

export default ExplorerSection
