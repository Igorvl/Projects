import React, { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import VortexEffect from '../components/VortexEffect'

export default function About() {
    return (
        <motion.div
            style={{ minHeight: '100vh', backgroundColor: 'black' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1 }}
        >
            {/* Fixed Background with Vortex Effect */}
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100vh', zIndex: 0 }}>
                <VortexEffect
                    imageSrc="/триптих-veil.png"
                    config={{
                        autoPlay: true,
                        loop: false,
                        reverseOnComplete: false,
                        duration: 2.3,
                        chromaticStrength: 5.0,
                        radius: 1.0
                    }}
                />
                <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.4)', pointerEvents: 'none' }} />
            </div>

            {/* Content Overlay */}
            <div style={{ position: 'relative', zIndex: 10, width: '100%', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
                <div style={{ marginTop: '20vh', color: 'white', textAlign: 'center', maxWidth: '800px' }}>
                    <h1 style={{ fontSize: '3rem', fontWeight: 300, letterSpacing: '0.2em', textTransform: 'uppercase', marginBottom: '2rem' }}>Frozen Tension</h1>
                    <p style={{ color: 'rgba(255,255,255,0.9)', fontSize: '1.5rem', fontStyle: 'italic', lineHeight: 1.6 }}>
                        "A study in structural drapery and the fluid dynamics of concrete casting flow."
                    </p>
                </div>

                {/* Additional content if needed */}
                <div style={{ marginTop: '5rem', maxWidth: '800px', color: 'rgba(255,255,255,0.7)', textAlign: 'center', lineHeight: 1.6 }}>
                    <p>
                        Our studio explores the boundaries between digital and physical forms, creating immersive experiences that challenge perception.
                    </p>
                </div>
            </div>
        </motion.div>
    )
}
