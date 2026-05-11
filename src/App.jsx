import { useState } from 'react'
import HeroSection from './components/HeroSection.jsx'
import ExplorerSection from './components/ExplorerSection.jsx'

function App() {
  const [view, setView] = useState('hero')

  return (
    <main>
      {view === 'hero'
        ? <HeroSection key="hero" onCTAClick={() => setView('explorer')} />
        : <ExplorerSection key="explorer" onHome={() => setView('hero')} />
      }
      <p className="credits">Données : <a target="_blank" href="https://www.infoflora.ch/">Info Flora</a> / Swiss National Databank of Vascular Plants, via <a target="_blank" href="https://www.gbif.org/">GBIF.org</a></p>
    </main>
  )
}

export default App
