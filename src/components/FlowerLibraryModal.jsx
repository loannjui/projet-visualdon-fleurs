import { useEffect, useRef } from 'react'
import fleurs from '../data/fleurs.js'

function FlowerLibraryModal({ isOpen, onClose }) {
  const modalRef = useRef(null)

  useEffect(() => {
    if (!isOpen) return
    const handleKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [isOpen, onClose])

  useEffect(() => {
    if (!isOpen) return
    const modal = modalRef.current
    if (!modal) return
    const blockBackground = (e) => {
      if (!modal.contains(e.target)) { e.preventDefault(); e.stopPropagation() }
    }
    const stopBubble = (e) => e.stopPropagation()
    window.addEventListener('wheel', blockBackground, { capture: true, passive: false })
    modal.addEventListener('wheel', stopBubble)
    return () => {
      window.removeEventListener('wheel', blockBackground, { capture: true })
      modal.removeEventListener('wheel', stopBubble)
    }
  }, [isOpen])

  if (!isOpen) return null

  const fleursParCouleur = fleurs.reduce((acc, fleur) => {
    const couleur = fleur.couleur || '#CCCCCC'
    if (!acc[couleur]) acc[couleur] = []
    acc[couleur].push(fleur)
    return acc
  }, {})

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="library-modal" ref={modalRef} onClick={e => e.stopPropagation()}>

        <div className="library-header">
          <span className="panel-title" style={{ fontSize: '1.1rem' }}>Répertoire des fleurs</span>
        </div>

        <div className="library-content">
          {Object.entries(fleursParCouleur).map(([couleur, groupe]) => (
            <section key={couleur} className="library-color-section">
              <div className="library-color-title">
                <span className="dominant-swatch" style={{ backgroundColor: couleur, width: 24, height: 24, flexShrink: 0 }} />
                <h3 className="modal-section-label" style={{ margin: 0 }}>{couleur}</h3>
              </div>
              <div className="library-grid">
                {groupe.map((fleur) => (
                  <article key={fleur.nom} className="library-card">
                    <img
                      src={fleur.image}
                      alt={fleur.nom}
                      onError={e => { e.target.style.display = 'none' }}
                    />
                    <div className="library-card-body">
                      <p className="library-card-name">{fleur.nom}</p>
                      <p className="library-card-species">{fleur.species}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>

        <button className="modal-close" onClick={onClose} aria-label="Fermer">✕</button>
      </div>
    </div>
  )
}

export default FlowerLibraryModal
