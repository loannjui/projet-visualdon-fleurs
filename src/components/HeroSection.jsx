import { useState } from 'react'
import ColorGrid from './ColorGrid.jsx'
import FlowerLibraryModal from './FlowerLibraryModal.jsx'

function HeroSection({ onCTAClick }) {
  const [mode, setMode] = useState('random')
  const [fading, setFading] = useState(false)
  const [isLibraryOpen, setIsLibraryOpen] = useState(false)

  const handleToggle = () => {
    setFading(true)
    setTimeout(() => {
      setMode(m => m === 'data' ? 'random' : 'data')
      setFading(false)
    }, 300)
  }

  return (
    <section className="hero-section">
      <ColorGrid key={mode} mode={mode} fading={fading} />
      {mode === 'data' && (
        <>
          <span className="axis-label axis-label--y">Altitude →</span>
          <span className="axis-label axis-label--x">Mois →</span>
        </>
      )}
      <button
        className="grid-mode-toggle"
        onClick={handleToggle}
      >
        {mode === 'data' ? 'Mode aléatoire' : 'Par altitude & mois'}
      </button>
      <FlowerLibraryModal isOpen={isLibraryOpen} onClose={() => setIsLibraryOpen(false)} />
      <div className={`hero-cta${mode === 'data' ? ' hero-cta--data' : ''}`}>
        <h1>Thalie — Le nuancier<br />des fleurs suisses.</h1>
        <p>La Suisse abrite plus de 3'000 espèces de plantes à fleurs, chacune avec sa couleur propre. De la ville aux montagnes, du premier crocus aux dernières gentianes d'automne, la palette change à chaque mètre et à chaque mois.</p>
        <p>Projet réalisé par <b>Teicir Bouazizi</b> et <b>Loann Juillerat</b>.</p>
        <button onClick={onCTAClick}>Commencer à explorer</button>
        <button onClick={() => setIsLibraryOpen(true)}>Voir toutes les fleurs</button>
      </div>
    </section>
  )
}

export default HeroSection
