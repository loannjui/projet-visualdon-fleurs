import { useState, useEffect, useRef } from 'react'
import { MOIS_COURTS } from '../data/fleurs'

function parseLocalisation(str) {
  if (!str) return []
  return str.split('\n').filter(Boolean).map(line => {
    const sep = line.indexOf(' : ')
    if (sep === -1) return { label: null, text: line }
    return { label: line.slice(0, sep), text: line.slice(sep + 3) }
  })
}

function FlowerModal({ flowers, onClose }) {
  const [activeTab, setActiveTab] = useState(0)
  const activeTabRef = useRef(null)
  const tabsRef = useRef(null)
  const cardRef = useRef(null)

  useEffect(() => { setActiveTab(0) }, [flowers])

  useEffect(() => {
    activeTabRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [activeTab])

  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  const isOpen = !!flowers && flowers.length > 0

  useEffect(() => {
    if (!isOpen) return
    const card = cardRef.current
    if (!card) return

    // Capture phase on window: block wheel events outside the modal card
    // (prevents both Lenis and native background scroll).
    const blockBackground = (e) => {
      if (!card.contains(e.target)) {
        e.preventDefault()
        e.stopPropagation()
      }
    }
    // Bubble phase on card: stop events from reaching Lenis's window listener.
    // No preventDefault → browser scrolls the card natively at full speed.
    const stopBubble = (e) => e.stopPropagation()

    window.addEventListener('wheel', blockBackground, { capture: true, passive: false })
    card.addEventListener('wheel', stopBubble)
    return () => {
      window.removeEventListener('wheel', blockBackground, { capture: true })
      card.removeEventListener('wheel', stopBubble)
    }
  }, [isOpen])

  if (!flowers || flowers.length === 0) return null

  const flower = flowers[activeTab] ?? flowers[0]
  const locations = parseLocalisation(flower.localisation)
  const total = flowers.length

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" ref={cardRef} onClick={e => e.stopPropagation()}>

        {/* Onglets + navigation */}
        <div className="modal-tabs-row" style={{ '--active-color': flower.couleur }}>
          {total > 1 && (
            <button
              className="modal-nav-btn"
              onClick={() => setActiveTab(i => (i - 1 + total) % total)}
              aria-label="Précédent"
            >‹</button>
          )}

          <div className="modal-tabs" ref={tabsRef}>
            {flowers.map((f, i) => (
              <button
                key={f.nom}
                ref={i === activeTab ? activeTabRef : null}
                className={`modal-tab${i === activeTab ? ' modal-tab--active' : ''}`}
                onClick={() => setActiveTab(i)}
              >
                {f.nom}
              </button>
            ))}
          </div>

          {total > 1 && (
            <button
              className="modal-nav-btn"
              onClick={() => setActiveTab(i => (i + 1) % total)}
              aria-label="Suivant"
            >›</button>
          )}
        </div>

        <div className="modal-body">

          {/* Photo + description */}
          <div className="modal-top">
            {flower.image && (
              <img
                src={flower.image}
                alt={flower.nom}
                className="modal-image"
                onError={e => { e.target.style.display = 'none' }}
              />
            )}
            <div className="modal-top-text">
              <p className="modal-species">{flower.species}</p>
              <p className="modal-description">{flower.description}</p>
            </div>
          </div>

          {/* Floraison */}
          {flower.mois_floraison?.length > 0 && (
            <div className="modal-section">
              <h3 className="modal-section-label">Floraison</h3>
              <p className="modal-section-text">
                {flower.mois_floraison.map(m => MOIS_COURTS[m]).join(' · ')}
              </p>
              {flower.floraison_str && (
                <p className="modal-section-text modal-floraison-str">{flower.floraison_str}</p>
              )}
            </div>
          )}

          {/* Où le trouver */}
          {locations.length > 0 && (
            <div className="modal-section">
              <h3 className="modal-section-label">Où les trouver ?</h3>
              {locations.map((loc, i) => (
                <div key={i} className="modal-location-block">
                  {loc.label && <strong className="modal-location-label">{loc.label}</strong>}
                  <p className="modal-section-text">{loc.text}</p>
                </div>
              ))}
            </div>
          )}

          {/* Altitude */}
          {flower.altitude && (
            <div className="modal-section">
              <h3 className="modal-section-label">Altitude</h3>
              <p className="modal-section-text">{flower.altitude.min} m – {flower.altitude.max} m</p>
            </div>
          )}

          {/* Fun fact */}
          {flower.fun_fact && (
            <div className="modal-section modal-funfact">
              <h3 className="modal-section-label">Le saviez-vous ?</h3>
              <p className="modal-section-text">{flower.fun_fact}</p>
            </div>
          )}
        </div>

        <button className="modal-close" onClick={onClose} aria-label="Fermer">✕</button>
      </div>
    </div>
  )
}

export default FlowerModal
