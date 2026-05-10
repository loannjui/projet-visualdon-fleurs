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
      <button
        className="grid-mode-toggle"
        onClick={handleToggle}
      >
        {mode === 'data' ? 'Mode aléatoire' : 'Par altitude & mois'}
      </button>
      <FlowerLibraryModal isOpen={isLibraryOpen} onClose={() => setIsLibraryOpen(false)} />
      <div className={`hero-cta${mode === 'data' ? ' hero-cta--data' : ''}`}>
        <h1>Le nuancier des fleurs<br />suisses.</h1>
        <p>La Suisse abrite plus de 3'000 espèces de plantes à fleurs, chacune avec sa couleur propre façonnée par son altitude et sa saison. Des prairies de plaine aux éboulis d'altitude, du premier crocus printanier aux dernières gentianes d'automne, la palette change à chaque mètre et à chaque semaine.</p>
        <button onClick={onCTAClick}>Commencer à explorer</button>
        <button onClick={() => setIsLibraryOpen(true)}>Voir toutes les fleurs</button>
      </div>
    </section>
  )
}

export default HeroSection
