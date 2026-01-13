import React, { useEffect, useState, useRef } from 'react'
import gsap from 'gsap'

/**
 * Custom Cursor - ExoApe style
 * Follows mouse with smooth lag, reacts to hoverable elements
 */
export default function CustomCursor() {
    const cursorRef = useRef(null)
    const cursorDotRef = useRef(null)
    const posRef = useRef({ x: 0, y: 0 })
    const velRef = useRef({ x: 0, y: 0 })

    useEffect(() => {
        const cursor = cursorRef.current
        const dot = cursorDotRef.current
        if (!cursor || !dot) return

        let rafId

        // Mouse position tracking
        const onMouseMove = (e) => {
            posRef.current = { x: e.clientX, y: e.clientY }
        }

        // Hover states
        const onMouseEnter = () => {
            gsap.to(cursor, {
                scale: 1.5,
                duration: 0.3,
            })
        }

        const onMouseLeave = () => {
            gsap.to(cursor, {
                scale: 1,
                duration: 0.3,
            })
        }

        const animate = () => {
            const { x, y } = posRef.current

            // Smooth follow with lag
            velRef.current.x += (x - velRef.current.x) * 0.08
            velRef.current.y += (y - velRef.current.y) * 0.08

            // Ring follows with offset (bottom-right)
            gsap.set(cursor, {
                x: velRef.current.x + 24,
                y: velRef.current.y + 24,
            })

            // Dot follows directly (centered)
            gsap.set(dot, {
                x: x,
                y: y,
            })

            rafId = requestAnimationFrame(animate)
        }

        // Add listeners
        document.addEventListener('mousemove', onMouseMove)

        // Interactive elements
        const interactives = document.querySelectorAll('a, button, [data-cursor="pointer"]')
        interactives.forEach(el => {
            el.addEventListener('mouseenter', onMouseEnter)
            el.addEventListener('mouseleave', onMouseLeave)
        })

        animate()

        return () => {
            if (rafId) cancelAnimationFrame(rafId)
            document.removeEventListener('mousemove', onMouseMove)
            interactives.forEach(el => {
                el.removeEventListener('mouseenter', onMouseEnter)
                el.removeEventListener('mouseleave', onMouseLeave)
            })
        }
    }, [])

    return (
        <>
            {/* Main cursor ring - Offset Bottom-Right */}
            <div
                ref={cursorRef}
                className="fixed top-0 left-0 rounded-full pointer-events-none z-[9999]"
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    width: '80px',
                    height: '80px',
                    borderRadius: '50%',
                    pointerEvents: 'none',
                    zIndex: 9999,
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    backdropFilter: 'blur(10px)',
                    WebkitBackdropFilter: 'blur(10px)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    // No translate(-50%, -50%) - so top-left corner is at (x+24, y+24)
                }}
            >
                <span style={{
                    fontSize: '10px',
                    color: 'rgba(255, 255, 255, 0.8)',
                    fontWeight: 500,
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase'
                }}>Scroll</span>
            </div>
            {/* Center dot */}
            <div
                ref={cursorDotRef}
                className="fixed top-0 left-0 rounded-full pointer-events-none z-[9999]"
                style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    width: '5px',
                    height: '5px',
                    borderRadius: '50%',
                    backgroundColor: 'white',
                    pointerEvents: 'none',
                    zIndex: 9999,
                    mixBlendMode: 'difference',
                    transform: 'translate(-50%, -50%)' // Dot stays centered on mouse
                }}
            />
        </>
    )
}
