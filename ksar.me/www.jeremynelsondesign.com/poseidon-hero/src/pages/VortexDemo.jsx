import React, { useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import VortexEffect from '../components/VortexEffect'

/**
 * VortexDemo Page
 * 
 * Magnifier Appear Effect Demo
 * - Circular reveal expanding from center
 * - Chromatic aberration on the edge
 * - Smooth expansion animation
 */

// Available images
const demoImages = [
    { src: '/guy.png', label: 'Guy' },
    { src: '/triptix.jpg', label: 'Triptix' },
    { src: '/ocean_waves_hero.png', label: 'Ocean' },
    { src: '/триптих-veil.png', label: 'Veil' }
]

export default function VortexDemo() {
    const [currentImage, setCurrentImage] = useState(demoImages[0].src)

    const [config, setConfig] = useState({
        radius: 1.0,
        chromaticStrength: 5.0,
        feather: 0.5,
        duration: 2.3,
        reverseDuration: 1.3,
        holdDuration: 2.0,
        initialDelay: 0.5,
        autoPlay: true,
        loop: true,
        loopDelay: 1.0,
        reverseOnComplete: true
    })

    const [showControls, setShowControls] = useState(true)

    const updateConfig = useCallback((key, value) => {
        setConfig(prev => ({ ...prev, [key]: value }))
    }, [])

    const triggerEffect = () => {
        if (window.triggerVortex) {
            window.triggerVortex()
        }
    }

    const Slider = ({ label, prop, min = 0, max = 5, step = 0.1 }) => (
        <div className="control-item">
            <div className="control-header">
                <span className="control-label">{label}</span>
                <span className="control-value">{config[prop].toFixed(2)}</span>
            </div>
            <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={config[prop]}
                onChange={(e) => updateConfig(prop, parseFloat(e.target.value))}
                className="control-slider"
            />
        </div>
    )

    const Toggle = ({ label, prop }) => (
        <div className="control-item toggle-item">
            <span className="control-label">{label}</span>
            <button
                className={`toggle-switch ${config[prop] ? 'active' : ''}`}
                onClick={() => updateConfig(prop, !config[prop])}
            >
                <span className="toggle-knob" />
                <span className="toggle-text">{config[prop] ? 'On' : 'Off'}</span>
            </button>
        </div>
    )

    return (
        <main className="vortex-demo-page">
            {/* Full-screen Effect */}
            <div className="vortex-canvas">
                <VortexEffect
                    key={currentImage}
                    imageSrc={currentImage}
                    config={config}
                />
            </div>

            {/* Header */}
            <motion.div
                className="demo-header"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3, duration: 0.6 }}
            >
                <div className="demo-title">
                    <h1>Magnifier<span className="accent">FX</span></h1>
                    <p>Circular Reveal Effect</p>
                </div>
                <div className="header-actions">
                    <button className="trigger-btn" onClick={triggerEffect}>
                        Trigger Effect
                    </button>
                    <button
                        className="controls-toggle"
                        onClick={() => setShowControls(!showControls)}
                    >
                        {showControls ? 'Hide' : 'Show'} Controls
                    </button>
                </div>
            </motion.div>

            {/* Controls Panel */}
            <motion.div
                className={`controls-panel ${showControls ? 'visible' : 'hidden'}`}
                initial={{ opacity: 0, x: 50 }}
                animate={{
                    opacity: showControls ? 1 : 0,
                    x: showControls ? 0 : 50
                }}
                transition={{ duration: 0.4 }}
            >
                <div className="controls-content">
                    {/* Image Selection */}
                    <div className="control-section">
                        <h3 className="section-title">Media</h3>
                        <div className="image-selector">
                            {demoImages.map((img) => (
                                <button
                                    key={img.src}
                                    className={`image-option ${currentImage === img.src ? 'active' : ''}`}
                                    onClick={() => setCurrentImage(img.src)}
                                >
                                    {img.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Effect Controls */}
                    <div className="control-section">
                        <h3 className="section-title">Effect</h3>
                        <Slider label="Radius" prop="radius" min={0.5} max={2} />
                        <Slider label="Chromatic" prop="chromaticStrength" max={8} />
                        <Slider label="Feather" prop="feather" min={0.1} max={3} />
                    </div>

                    {/* Timing Controls */}
                    <div className="control-section">
                        <h3 className="section-title">Timing</h3>
                        <Slider label="Duration" prop="duration" min={0.3} max={4} />
                        <Slider label="Reverse Duration" prop="reverseDuration" min={0.3} max={4} />
                        <Slider label="Hold Duration" prop="holdDuration" min={0} max={5} />
                        <Slider label="Initial Delay" prop="initialDelay" min={0} max={3} />
                        <Slider label="Loop Delay" prop="loopDelay" min={0.5} max={5} />
                    </div>

                    {/* Toggles */}
                    <div className="control-section">
                        <h3 className="section-title">Playback</h3>
                        <Toggle label="Auto Play" prop="autoPlay" />
                        <Toggle label="Loop" prop="loop" />
                        <Toggle label="Reverse" prop="reverseOnComplete" />
                    </div>
                </div>
            </motion.div>

            {/* Info */}
            <motion.div
                className="demo-info"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.8, duration: 0.6 }}
            >
                <p>Circular reveal with chromatic aberration</p>
            </motion.div>

            <style>{`
                .vortex-demo-page {
                    position: relative;
                    width: 100vw;
                    height: 100vh;
                    background: #000;
                    overflow: hidden;
                }

                .vortex-canvas {
                    position: absolute;
                    inset: 0;
                    z-index: 1;
                }

                .demo-header {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    z-index: 100;
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    padding: 2rem 3rem;
                    pointer-events: none;
                }

                .demo-title {
                    pointer-events: auto;
                }

                .demo-title h1 {
                    font-size: 2.5rem;
                    font-weight: 200;
                    letter-spacing: 0.05em;
                    color: white;
                    margin: 0;
                    text-shadow: 0 2px 20px rgba(0,0,0,0.5);
                }

                .demo-title .accent {
                    color: #00d4ff;
                    font-weight: 400;
                }

                .demo-title p {
                    font-size: 0.9rem;
                    color: rgba(255,255,255,0.6);
                    margin-top: 0.3rem;
                    letter-spacing: 0.1em;
                    text-transform: uppercase;
                }

                .header-actions {
                    display: flex;
                    gap: 1rem;
                    pointer-events: auto;
                }

                .trigger-btn {
                    background: linear-gradient(135deg, #00d4ff, #0099cc);
                    border: none;
                    color: white;
                    padding: 0.75rem 1.5rem;
                    border-radius: 8px;
                    font-size: 0.85rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                }

                .trigger-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 20px rgba(0, 212, 255, 0.4);
                }

                .controls-toggle {
                    background: rgba(255,255,255,0.1);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255,255,255,0.15);
                    color: white;
                    padding: 0.75rem 1.5rem;
                    border-radius: 8px;
                    font-size: 0.85rem;
                    font-weight: 500;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }

                .controls-toggle:hover {
                    background: rgba(255,255,255,0.2);
                }

                .controls-panel {
                    position: absolute;
                    top: 80px;
                    right: 20px;
                    bottom: 80px;
                    width: 320px;
                    z-index: 50;
                    pointer-events: auto;
                }

                .controls-panel.hidden {
                    pointer-events: none;
                }

                .controls-content {
                    height: 100%;
                    background: rgba(15, 15, 20, 0.9);
                    backdrop-filter: blur(20px);
                    border: 1px solid rgba(0, 212, 255, 0.2);
                    border-radius: 16px;
                    padding: 1.5rem;
                    overflow-y: auto;
                }

                .control-section {
                    margin-bottom: 1.5rem;
                }

                .section-title {
                    font-size: 0.75rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.15em;
                    color: #00d4ff;
                    margin-bottom: 1rem;
                    padding-bottom: 0.5rem;
                    border-bottom: 1px solid rgba(0, 212, 255, 0.2);
                }

                .control-item {
                    margin-bottom: 1rem;
                }

                .control-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 0.5rem;
                }

                .control-label {
                    font-size: 0.85rem;
                    color: rgba(255,255,255,0.85);
                    font-weight: 500;
                }

                .control-value {
                    font-size: 0.75rem;
                    color: rgba(255,255,255,0.5);
                    font-family: 'JetBrains Mono', monospace;
                    background: rgba(0, 212, 255, 0.1);
                    padding: 0.2rem 0.5rem;
                    border-radius: 4px;
                }

                .control-slider {
                    width: 100%;
                    height: 4px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 2px;
                    outline: none;
                    -webkit-appearance: none;
                    cursor: pointer;
                }

                .control-slider::-webkit-slider-thumb {
                    -webkit-appearance: none;
                    width: 16px;
                    height: 16px;
                    background: linear-gradient(135deg, #00d4ff, #0099cc);
                    border-radius: 50%;
                    cursor: pointer;
                }

                .toggle-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .toggle-switch {
                    position: relative;
                    width: 60px;
                    height: 28px;
                    background: rgba(255,255,255,0.1);
                    border: 1px solid rgba(255,255,255,0.15);
                    border-radius: 14px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                }

                .toggle-switch.active {
                    background: linear-gradient(135deg, rgba(0, 212, 255, 0.3), rgba(0, 153, 204, 0.3));
                    border-color: #00d4ff;
                }

                .toggle-knob {
                    position: absolute;
                    top: 3px;
                    left: 3px;
                    width: 20px;
                    height: 20px;
                    background: white;
                    border-radius: 50%;
                    transition: transform 0.3s ease;
                }

                .toggle-switch.active .toggle-knob {
                    transform: translateX(32px);
                    background: linear-gradient(135deg, #00d4ff, #0099cc);
                }

                .toggle-text {
                    position: absolute;
                    right: 8px;
                    top: 50%;
                    transform: translateY(-50%);
                    font-size: 0.65rem;
                    color: rgba(255,255,255,0.5);
                }

                .toggle-switch.active .toggle-text {
                    left: 8px;
                    right: auto;
                    color: #00d4ff;
                }

                .image-selector {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 0.5rem;
                }

                .image-option {
                    padding: 0.5rem;
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 6px;
                    color: rgba(255,255,255,0.7);
                    font-size: 0.75rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }

                .image-option:hover {
                    background: rgba(255,255,255,0.1);
                }

                .image-option.active {
                    background: linear-gradient(135deg, rgba(0, 212, 255, 0.2), rgba(0, 153, 204, 0.2));
                    border-color: #00d4ff;
                    color: white;
                }

                .demo-info {
                    position: absolute;
                    bottom: 2rem;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 100;
                }

                .demo-info p {
                    font-size: 0.9rem;
                    color: rgba(255,255,255,0.4);
                    letter-spacing: 0.05em;
                }
            `}</style>
        </main>
    )
}
