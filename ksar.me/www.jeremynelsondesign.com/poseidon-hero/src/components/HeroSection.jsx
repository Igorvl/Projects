import React, { useRef, useEffect } from 'react'

export default function HeroSection() {
    return (
        <section
            style={{
                position: 'relative',
                width: '100%',
                height: '100vh',
                overflow: 'hidden',
                backgroundColor: 'black'
            }}
            data-cursor="blend"
        >
            {/* Background Image */}
            <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                zIndex: 0
            }}>
                <img
                    src="/ocean_waves_hero.png"
                    alt="Hero Background"
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        opacity: 0.8
                    }}
                />
            </div>

            {/* Vignette */}
            <div
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: '100%',
                    pointerEvents: 'none',
                    zIndex: 1,
                    background: 'radial-gradient(ellipse at center, transparent 0%, transparent 50%, rgba(0,0,0,0.5) 100%)'
                }}
            />

            {/* Title - Bottom Left */}
            <div style={{
                position: 'absolute',
                bottom: '5vh',
                left: '5vw',
                zIndex: 10,
                textAlign: 'left',
                color: 'white'
            }}>
                <h1 style={{
                    fontSize: 'clamp(3rem, 8vw, 6rem)',
                    fontWeight: '800',
                    lineHeight: '0.9',
                    textTransform: 'uppercase',
                    margin: 0,
                    fontFamily: "'Outfit', sans-serif" // Fallback to sans-serif if font missing
                }}>
                    Synthetic<br />
                    Architect
                </h1>
                <div style={{
                    marginTop: '1.5rem',
                    fontSize: '1rem',
                    letterSpacing: '0.4em',
                    textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.7)'
                }}>
                    Designing the Future
                </div>
            </div>

            {/* Status & Scroll Line - Bottom Right */}
            <div style={{
                position: 'absolute',
                bottom: '5vh',
                right: '5vw',
                zIndex: 10,
                display: 'flex',
                alignItems: 'flex-end',
                gap: '2rem'
            }}>
                {/* Status Text */}
                <div style={{
                    textAlign: 'right',
                    fontSize: '12px',
                    letterSpacing: '0.15em',
                    textTransform: 'uppercase',
                    lineHeight: '1.6',
                    fontFamily: "'JetBrains Mono', monospace",
                    color: 'rgba(255,255,255,0.5)'
                }}>
                    <div>
                        SYSTEM: <span style={{ color: 'white' }}>ONLINE</span>
                    </div>
                    <div>
                        LOC: <span style={{ color: 'white' }}>DUBAI</span>
                    </div>
                </div>

                {/* Vertical Scroll Line */}
                <div style={{
                    width: '1px',
                    height: '100px',
                    backgroundColor: 'rgba(255,255,255,0.3)',
                    position: 'relative'
                }}>
                    {/* Animated Pulse (optional, simple CSS) */}
                    <div style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '30%',
                        backgroundColor: 'white',
                        animation: 'scrollPulse 2s infinite'
                    }} />
                </div>
            </div>

            <style>{`
                @keyframes scrollPulse {
                    0% { top: 0; opacity: 0; }
                    50% { opacity: 1; }
                    100% { top: 100%; opacity: 0; }
                }
            `}</style>
        </section>
    )
}
