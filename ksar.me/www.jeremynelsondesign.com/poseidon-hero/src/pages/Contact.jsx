import React from 'react'
import { motion } from 'framer-motion'
import VortexEffect from '../components/VortexEffect'

export default function Contact() {
    return (
        <motion.main
            style={{ minHeight: '100vh', backgroundColor: 'black' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
        >
            {/* Fixed Background with Vortex Effect */}
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100vh', zIndex: 0 }}>
                <VortexEffect
                    imageSrc="/триптих-MANOR+logo 2.jpg"
                    config={{
                        autoPlay: true,
                        loop: false,
                        reverseOnComplete: false,
                        duration: 2.3,
                        chromaticStrength: 5.0,
                        radius: 1.0
                    }}
                />
                <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.5)', pointerEvents: 'none' }} />
            </div>

            {/* Scrollable Content Overlay */}
            <div style={{ position: 'relative', zIndex: 10, width: '100%' }}>

                {/* Hero Section (Title) */}
                <section style={{ height: '100vh', width: '100%', display: 'flex', alignItems: 'flex-end', padding: '3rem' }}>
                    <div style={{ marginBottom: '3rem' }}>
                        <h1 style={{ fontSize: '4rem', fontWeight: '800', color: 'white', marginBottom: '1rem', lineHeight: 1, textTransform: 'uppercase' }}>Contact</h1>
                        <p style={{ fontSize: '1.25rem', color: 'rgba(255,255,255,0.8)', letterSpacing: '0.05em' }}>Get in touch with us</p>
                    </div>
                </section>

                {/* Details Section */}
                <section style={{
                    maxWidth: '1200px',
                    margin: '0 auto',
                    padding: '0 2rem 10rem',
                    background: 'linear-gradient(to bottom, transparent, rgba(0,0,0,0.8) 100px)'
                }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4rem' }}>
                        <div>
                            <h2 style={{ fontSize: '2rem', color: 'white', fontWeight: 300, marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '1rem' }}>Let's Connect</h2>
                            <p style={{ fontSize: '1.125rem', color: 'rgba(255,255,255,0.8)', lineHeight: 1.6, marginBottom: '2rem' }}>
                                We're always interested in new projects and collaborations.
                                Reach out to discuss how we can work together.
                            </p>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '1.125rem' }}>
                                <p style={{ color: 'rgba(255,255,255,0.7)' }}>
                                    <span style={{ color: 'white', fontWeight: 500 }}>Email:</span> hello@poseidon.studio
                                </p>
                                <p style={{ color: 'rgba(255,255,255,0.7)' }}>
                                    <span style={{ color: 'white', fontWeight: 500 }}>Location:</span> Dubai, UAE
                                </p>
                            </div>
                        </div>
                        <div>
                            <h2 style={{ fontSize: '2rem', color: 'white', fontWeight: 300, marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.2)', paddingBottom: '1rem' }}>Studio Hours</h2>
                            <p style={{ fontSize: '1.125rem', color: 'rgba(255,255,255,0.8)', lineHeight: 1.6 }}>
                                Monday – Friday: 9:00 AM – 6:00 PM<br />
                                Saturday: By appointment<br />
                                Sunday: Closed
                            </p>
                        </div>
                    </div>
                </section>
            </div>
        </motion.main>
    )
}
