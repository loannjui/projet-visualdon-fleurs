import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import Lenis from 'lenis'
import 'normalize.css'
import './css/style.css'
import App from './App.jsx'

window.lenis = new Lenis({
  duration: 4,
  easing: t => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
})

function raf(time) {
  window.lenis.raf(time)
  requestAnimationFrame(raf)
}
requestAnimationFrame(raf)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
