import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import Lenis from '@studio-freight/lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

// Components
import CustomCursor from './components/CustomCursor'
import MagnifierTransition from './components/MagnifierTransition'
import Home from './pages/Home'
import About from './pages/About'
import Projects from './pages/Projects'
import Contact from './pages/Contact'
import GenericPage from './pages/GenericPage'
import MagnifierDemo from './pages/MagnifierDemo'
import VortexDemo from './pages/VortexDemo'
import ElementzDemo from './pages/ElementzDemo'
import './index.css'

gsap.registerPlugin(ScrollTrigger)

function App() {
  const [currentPage, setCurrentPage] = useState('elementz')
  const [transitionPhase, setTransitionPhase] = useState(null) // 'out' | 'in' | null
  const [pendingPage, setPendingPage] = useState(null)

  useEffect(() => {
    // Initialize Lenis smooth scroll
    const lenis = new Lenis({
      duration: 1.2,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      smoothWheel: true,
    })

    lenis.on('scroll', ScrollTrigger.update)

    gsap.ticker.add((time) => {
      lenis.raf(time * 1000)
    })
    gsap.ticker.lagSmoothing(0)

    return () => {
      lenis.destroy()
      gsap.ticker.remove(lenis.raf)
    }
  }, [])

  // Nav Handlers
  const handleNavClick = (e, item) => {
    e.preventDefault()
    const target = item.toLowerCase()

    if (target === currentPage || transitionPhase) return

    // Skip transition animation for WebGL demo pages
    if (target === 'magnifier' || currentPage === 'magnifier' ||
      target === 'vortex' || currentPage === 'vortex' ||
      target === 'elementz' || currentPage === 'elementz') {
      setCurrentPage(target)
      window.scrollTo(0, 0)
      return
    }

    setPendingPage(target)
    setTransitionPhase('out') // Start exit transition
  }

  // Called when 'out' phase completes - switch page and start 'in' phase
  const handleOutComplete = () => {
    setCurrentPage(pendingPage)
    window.scrollTo(0, 0)
    setTransitionPhase('in') // Start enter transition
  }

  // Called when 'in' phase completes - cleanup
  const handleInComplete = () => {
    setTransitionPhase(null)
    setPendingPage(null)
  }

  return (
    <>
      <CustomCursor />

      {/* Classic Header: Logo left, Nav right */}
      <header className="site-header">
        <div className="header-container">
          {/* Logo - Left */}
          <a href="#" className="header-logo" onClick={(e) => handleNavClick(e, 'home')}>
            <img src="/zeus.png" alt="Poseidon Logo" />
          </a>

          {/* Navigation - Right */}
          <nav className="header-nav">
            <ul className="nav-links">
              <li>
                <a
                  href="#"
                  onClick={(e) => handleNavClick(e, 'home')}
                  className={currentPage === 'home' ? 'active' : ''}
                >
                  Home
                </a>
              </li>
              <li>
                <a
                  href="#"
                  onClick={(e) => handleNavClick(e, 'projects')}
                  className={currentPage === 'projects' ? 'active' : ''}
                >
                  Projects
                </a>
              </li>
              <li>
                <a
                  href="#"
                  onClick={(e) => handleNavClick(e, 'about')}
                  className={currentPage === 'about' ? 'active' : ''}
                >
                  About
                </a>
              </li>
              <li>
                <a
                  href="#"
                  onClick={(e) => handleNavClick(e, 'contact')}
                  className={currentPage === 'contact' ? 'active' : ''}
                >
                  Contact
                </a>
              </li>
              <li>
                <a
                  href="#"
                  onClick={(e) => handleNavClick(e, 'magnifier')}
                  className={currentPage === 'magnifier' ? 'active' : ''}
                >
                  Magnifier
                </a>
              </li>
              <li>
                <a
                  href="#"
                  onClick={(e) => handleNavClick(e, 'vortex')}
                  className={currentPage === 'vortex' ? 'active' : ''}
                >
                  Vortex
                </a>
              </li>
              <li>
                <a
                  href="#"
                  onClick={(e) => handleNavClick(e, 'elementz')}
                  className={currentPage === 'elementz' ? 'active' : ''}
                >
                  Elementz
                </a>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      {/* Dynamic Magnifier Transition */}
      <MagnifierTransition
        phase={transitionPhase}
        onOutComplete={handleOutComplete}
        onInComplete={handleInComplete}
      />

      {/* Page Content Rendering */}
      <AnimatePresence mode="wait">
        {currentPage === 'home' && <Home key="home" />}
        {currentPage === 'projects' && <Projects key="projects" />}
        {currentPage === 'about' && <About key="about" />}
        {currentPage === 'terms' && <GenericPage key="terms" title="Terms" />}
        {currentPage === 'resources' && <GenericPage key="resources" title="Resources" />}
        {currentPage === 'contact' && <Contact key="contact" />}
        {currentPage === 'magnifier' && <MagnifierDemo key="magnifier" />}
        {currentPage === 'vortex' && <VortexDemo key="vortex" />}
        {currentPage === 'elementz' && <ElementzDemo key="elementz" />}
      </AnimatePresence>
    </>
  )
}

export default App
