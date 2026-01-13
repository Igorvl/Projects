import React, { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import MagnifierEffect from '../components/MagnifierEffect'

/**
 * MagnifierDemo Page
 * 
 * Full-page demonstration of the Magnifier+ liquid distortion effect
 * with interactive property controls matching Reveals.cool interface
 */

// Available images for demo
const demoImages = [
    { src: '/triptix.jpg', label: 'Triptix' },
    { src: '/ocean_waves_hero.png', label: 'Ocean Waves' },
    { src: '/триптих-veil.png', label: 'Veil' },
    { src: '/триптих-MANOR+logo 2.jpg', label: 'Manor' }
]

export default function MagnifierDemo() {
    // Current image
    const [currentImage, setCurrentImage] = useState(demoImages[0].src)

    // Magnifier configuration state
    const [config, setConfig] = useState({
        radius: 0.5,
        strength: 3.0,
        space: 0.5,
        disturbance: 0.4,
        feather: 1.0,
        threshold: 0.2,
        compensation: 1.0,
        dispersion: 1.0,
        scale: 1.0,
        fadeIn: false,
        fadeOutDelay: 1,
        fadeOutDuration: 2,
        sequence: false
    })

    // Controls panel visibility
    const [showControls, setShowControls] = useState(true)

    // Follow cursor toggle
    const [followCursor, setFollowCursor] = useState(false)

    // Update config handler
    const updateConfig = useCallback((key, value) => {
        setConfig(prev => ({ ...prev, [key]: value }))
    }, [])

    // Slider component for controls
    const Slider = ({ label, prop, min = 0, max = 1, step = 0.01, advanced = false }) => (
        <div className={`control-item ${advanced ? 'advanced' : ''}`}>
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

    // Toggle switch component
    const Toggle = ({ label, prop }) => (
        <div className="control-item toggle-item">
            <span className="control-label">{label}</span>
            <button
                className={`toggle-switch ${config[prop] ? 'active' : ''}`}
                onClick={() => updateConfig(prop, !config[prop])}
            >
                <span className="toggle-knob" />
                <span className="toggle-text">{config[prop] ? 'Yes' : 'No'}</span>
            </button>
        </div>
    )

    return (
        <main className="magnifier-demo-page">
            <div className="magnifier-canvas">
                <MagnifierEffect
                    key={currentImage} // Re-mount on image change for fadeIn
                    imageSrc={currentImage}
                    config={config}
                    followCursor={followCursor}
                />
            </div>

            {/* Header overlay */}
            <motion.div
                className="demo-header"
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.5, duration: 0.6 }}
            >
                <div className="demo-title">
                    <h1>Magnifier<span className="plus">+</span></h1>
                    <p>Liquid Distortion Effect</p>
                </div>
                <button
                    className="controls-toggle"
                    onClick={() => setShowControls(!showControls)}
                >
                    {showControls ? 'Hide Controls' : 'Show Controls'}
                </button>
            </motion.div>

            {/* Property Controls Panel */}
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

                    {/* Basic Controls */}
                    <div className="control-section">
                        <h3 className="section-title">Distortion</h3>
                        <Slider label="Radius" prop="radius" />
                        <Slider label="Strength" prop="strength" />
                        <Slider label="Space" prop="space" />
                        <Slider label="Disturbance" prop="disturbance" />
                    </div>

                    {/* Advanced Controls */}
                    <div className="control-section">
                        <h3 className="section-title">Advance</h3>
                        <Slider label="Feather" prop="feather" advanced />
                        <Slider label="Threshold" prop="threshold" advanced />
                        <Slider label="Compensation" prop="compensation" advanced />
                        <Slider label="Dispersion" prop="dispersion" advanced />
                        <Slider label="Scale" prop="scale" advanced />
                    </div>

                    {/* Toggles */}
                    <div className="control-section">
                        <h3 className="section-title">Animation</h3>
                        <Toggle label="Fade In" prop="fadeIn" />
                        <Toggle label="Sequence Mode" prop="sequence" />

                        {/* Follow Cursor toggle (separate state) */}
                        <div className="control-item toggle-item">
                            <span className="control-label">Follow Cursor</span>
                            <button
                                className={`toggle-switch ${followCursor ? 'active' : ''}`}
                                onClick={() => setFollowCursor(!followCursor)}
                            >
                                <span className="toggle-knob" />
                                <span className="toggle-text">{followCursor ? 'Yes' : 'No'}</span>
                            </button>
                        </div>
                    </div>
                </div>
            </motion.div>

            {/* Info overlay */}
            <motion.div
                className="demo-info"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.8, duration: 0.6 }}
            >
                <p>Move your cursor to interact with the liquid distortion</p>
            </motion.div>

            <style>{`
                .magnifier-demo-page {
                    position: relative;
                    width: 100vw;
                    height: 100vh;
                    background: #0a0a0a;
                    overflow: hidden;
                }

                .magnifier-canvas {
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

                .demo-title .plus {
                    color: #4D9FFF;
                    font-weight: 300;
                }

                .demo-title p {
                    font-size: 0.9rem;
                    color: rgba(255,255,255,0.6);
                    margin-top: 0.3rem;
                    letter-spacing: 0.1em;
                    text-transform: uppercase;
                }

                .controls-toggle {
                    pointer-events: auto;
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
                    transform: translateY(-2px);
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
                    background: rgba(15, 15, 20, 0.85);
                    backdrop-filter: blur(20px);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 16px;
                    padding: 1.5rem;
                    overflow-y: auto;
                    scrollbar-width: thin;
                    scrollbar-color: rgba(255,255,255,0.2) transparent;
                }

                .controls-content::-webkit-scrollbar {
                    display: block;
                    width: 6px;
                }

                .controls-content::-webkit-scrollbar-thumb {
                    background: rgba(255,255,255,0.2);
                    border-radius: 3px;
                }

                .control-section {
                    margin-bottom: 1.5rem;
                }

                .section-title {
                    font-size: 0.75rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.15em;
                    color: rgba(255,255,255,0.5);
                    margin-bottom: 1rem;
                    padding-bottom: 0.5rem;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                }

                .control-item {
                    margin-bottom: 1rem;
                }

                .control-item.advanced .control-label {
                    color: rgba(77, 159, 255, 0.8);
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
                    background: rgba(255,255,255,0.05);
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
                    background: linear-gradient(135deg, #4D9FFF, #AB47FF);
                    border-radius: 50%;
                    cursor: pointer;
                    transition: transform 0.2s ease;
                }

                .control-slider::-webkit-slider-thumb:hover {
                    transform: scale(1.2);
                }

                .control-slider::-moz-range-thumb {
                    width: 16px;
                    height: 16px;
                    background: linear-gradient(135deg, #4D9FFF, #AB47FF);
                    border-radius: 50%;
                    border: none;
                    cursor: pointer;
                }

                .toggle-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }

                .toggle-switch {
                    position: relative;
                    width: 70px;
                    height: 32px;
                    background: rgba(255,255,255,0.1);
                    border: 1px solid rgba(255,255,255,0.15);
                    border-radius: 16px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    overflow: hidden;
                }

                .toggle-switch.active {
                    background: linear-gradient(135deg, rgba(77,159,255,0.3), rgba(171,71,255,0.3));
                    border-color: rgba(77,159,255,0.5);
                }

                .toggle-knob {
                    position: absolute;
                    top: 4px;
                    left: 4px;
                    width: 22px;
                    height: 22px;
                    background: white;
                    border-radius: 50%;
                    transition: transform 0.3s ease;
                }

                .toggle-switch.active .toggle-knob {
                    transform: translateX(38px);
                    background: linear-gradient(135deg, #4D9FFF, #AB47FF);
                }

                .toggle-text {
                    position: absolute;
                    right: 10px;
                    top: 50%;
                    transform: translateY(-50%);
                    font-size: 0.7rem;
                    color: rgba(255,255,255,0.6);
                    font-weight: 500;
                }

                .toggle-switch.active .toggle-text {
                    left: 10px;
                    right: auto;
                    color: #4D9FFF;
                }

                .image-selector {
                    display: grid;
                    grid-template-columns: repeat(2, 1fr);
                    gap: 0.5rem;
                }

                .image-option {
                    padding: 0.6rem 0.8rem;
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 8px;
                    color: rgba(255,255,255,0.7);
                    font-size: 0.8rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }

                .image-option:hover {
                    background: rgba(255,255,255,0.1);
                    border-color: rgba(255,255,255,0.2);
                }

                .image-option.active {
                    background: linear-gradient(135deg, rgba(77,159,255,0.2), rgba(171,71,255,0.2));
                    border-color: #4D9FFF;
                    color: white;
                }

                .demo-info {
                    position: absolute;
                    bottom: 2rem;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 100;
                    text-align: center;
                }

                .demo-info p {
                    font-size: 0.9rem;
                    color: rgba(255,255,255,0.5);
                    letter-spacing: 0.05em;
                    text-shadow: 0 2px 10px rgba(0,0,0,0.5);
                }

                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }

                /* Mobile adjustments */
                @media (max-width: 768px) {
                    .controls-panel {
                        width: 280px;
                        right: 10px;
                    }

                    .demo-header {
                        padding: 1.5rem;
                    }

                    .demo-title h1 {
                        font-size: 1.8rem;
                    }
                }
            `}</style>
        </main>
    )
}
