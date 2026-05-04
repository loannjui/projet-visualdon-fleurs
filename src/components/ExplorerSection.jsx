import { useState, useEffect, useRef, useMemo } from 'react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useFlowerFilter } from '../hooks/useFlowerFilter'
import { updateAllLayers } from '../utils/updateSVGColors'
import MonthSlider from './MonthSlider.jsx'
import AltitudeSlider from './AltitudeSlider.jsx'
import ExportButton from './ExportButton.jsx'
import FlowerModal from './FlowerModal.jsx'
import MontagneIllustration from '../illustrations/montagne.svg?react'
import PlaineIllustration from '../illustrations/plaine.svg?react'
import VilleIllustration from '../illustrations/ville.svg?react'

gsap.registerPlugin(ScrollTrigger)

function ExplorerSection() {
  const [altitude, setAltitude] = useState(3786)
  const [month, setMonth] = useState(6)
  const [selectedFlowers, setSelectedFlowers] = useState([])
  const [shapeToFlower, setShapeToFlower] = useState({})

  const montRef    = useRef(null)
  const plaineRef  = useRef(null)
  const villeRef   = useRef(null)
  const flowersRef = useRef([])

  const { flowers } = useFlowerFilter(altitude, month)

  useEffect(() => { flowersRef.current = flowers }, [flowers])

  const displayedColors = useMemo(() =>
    [...new Set(Object.values(shapeToFlower).map(f => f.couleur))].slice(0, 12)
  , [shapeToFlower])

  const swatchRows = Math.max(1, Math.ceil(displayedColors.length / 6))
  const swatchMaxH = swatchRows * 52 + (swatchRows - 1) * 10 + 10 + 12

  useEffect(() => {
    const mapping = updateAllLayers(flowers)
    setShapeToFlower(mapping)
  }, [flowers])

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

  // Léger parallaxe sur chaque couche — le SVG glisse légèrement plus lentement que le scroll
  useEffect(() => {
    const ctx = gsap.context(() => {
      [montRef, plaineRef, villeRef].forEach(ref => {
        const svg = ref.current?.querySelector('svg')
        if (!svg) return
        gsap.fromTo(svg,
          { y: '0%' },
          {
            y: '-8%',
            ease: 'none',
            scrollTrigger: {
              trigger: ref.current,
              start: 'top bottom',
              end: 'bottom top',
              scrub: true,
            },
          }
        )
      })
    })
    return () => ctx.revert()
  }, [])

  return (
    <section className="explorer-section">

      {/* Panneaux de contrôle — fixes sur l'écran pendant tout le scroll */}
      <div className="controls-overlay">
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
                  const seen = new Set()
                  const flowers = Object.values(shapeToFlower).filter(f => {
                    if (f.couleur !== color || seen.has(f.nom)) return false
                    seen.add(f.nom)
                    return true
                  })
                  setSelectedFlowers(flowers)
                }}
              />
            ))}
          </div>
        </div>

        <AltitudeSlider value={altitude} />
        <MonthSlider value={month} onChange={setMonth} />
      </div>

      {/* Les 3 SVGs empilés — scroll naturel à travers chacun */}
      <div className="layer-wrap" ref={montRef}>
        <MontagneIllustration className="svg-layer" />
      </div>
      <div className="layer-wrap" ref={plaineRef}>
        <PlaineIllustration className="svg-layer" />
      </div>
      <div className="layer-wrap" ref={villeRef}>
        <VilleIllustration className="svg-layer" />
      </div>

      <FlowerModal flowers={selectedFlowers} onClose={() => setSelectedFlowers([])} />
    </section>
  )
}

export default ExplorerSection
