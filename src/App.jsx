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
    </main>
  )
}

export default App
