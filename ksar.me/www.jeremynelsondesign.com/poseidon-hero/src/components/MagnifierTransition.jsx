import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import gsap from 'gsap'

// Magnifier+ Liquid Distortion Shader (Based on Reveals.cool effect)
const fragmentShader = `
precision highp float;

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform vec2 uMouse;
uniform float uRadius;
uniform float uStrength;
uniform float uSpace;
uniform float uDisturbance;
uniform float uFeather;
uniform float uThreshold;
uniform float uCompensation;
uniform float uDispersion;
uniform float uScale;
uniform float uProgress;
uniform float uFadeIn;

varying vec2 vUv;

// Noise function for disturbance
float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void main() {
    vec2 uv = vUv;
    
    // Aspect ratio correction
    float aspect = uResolution.x / uResolution.y;
    vec2 uvAspect = uv;
    uvAspect.x *= aspect;
    vec2 mouseAspect = uMouse;
    mouseAspect.x *= aspect;
    
    // Distance from mouse/center
    float dist = distance(uvAspect, mouseAspect);
    
    // Animated radius based on progress
    float maxRadius = uRadius * max(aspect, 1.0);
    float currentRadius = maxRadius * uProgress;
    
    // Feathering calculation
    float featherStart = currentRadius * uThreshold;
    float featherEnd = currentRadius * (1.0 + uCompensation);
    float mask = 1.0 - smoothstep(featherStart, featherEnd, dist);
    mask = pow(mask, uFeather + 0.1);
    
    // Space (center flatness)
    float spaceRadius = currentRadius * uSpace;
    float spaceMask = smoothstep(0.0, spaceRadius, dist);
    
    // Disturbance (surface texture)
    float disturbNoise = noise(uv * 20.0 + uProgress * 5.0) * 2.0 - 1.0;
    disturbNoise += noise(uv * 40.0 - uProgress * 3.0) * 0.5;
    float disturbance = disturbNoise * uDisturbance * mask * spaceMask * 0.02;
    
    // Direction from center
    vec2 dir = normalize(uv - uMouse + 0.0001);
    
    // Magnification/Scale effect
    float magnification = 1.0 + (uScale - 1.0) * mask;
    
    // Liquid distortion strength
    float distortAmount = uStrength * mask * spaceMask;
    
    // Calculate distorted UV
    vec2 distortedUv = uMouse + (uv - uMouse) / magnification;
    
    // Add wave-like distortion
    float wave = sin(dist * 15.0 - uProgress * 10.0) * 0.5 + 0.5;
    distortedUv += dir * distortAmount * wave * 0.1;
    distortedUv += dir * disturbance;
    
    // Chromatic dispersion at edges
    float dispersionAmount = uDispersion * mask * (1.0 - spaceMask) * 0.015;
    
    vec2 redOffset = distortedUv + dir * dispersionAmount;
    vec2 greenOffset = distortedUv;
    vec2 blueOffset = distortedUv - dir * dispersionAmount;
    
    // Sample texture with chromatic aberration
    float r = texture2D(uTexture, redOffset).r;
    float g = texture2D(uTexture, greenOffset).g;
    float b = texture2D(uTexture, blueOffset).b;
    
    vec3 color = vec3(r, g, b);
    
    // Fade in effect
    float fadeAlpha = uFadeIn > 0.5 ? smoothstep(0.0, 0.3, uProgress) : 1.0;
    
    // Subtle vignette inside magnifier for depth
    float vignette = 1.0 - (mask * 0.1);
    color *= vignette;
    
    gl_FragColor = vec4(color, fadeAlpha);
}
`

const vertexShader = `
varying vec2 vUv;
void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

function MagnifierEffect({ texture, progress, mousePos, config }) {
    const { size, viewport } = useThree()
    const shaderRef = useRef()

    const uniforms = useMemo(() => ({
        uTexture: { value: texture },
        uResolution: { value: new THREE.Vector2(size.width, size.height) },
        uMouse: { value: new THREE.Vector2(mousePos.x, mousePos.y) },
        uRadius: { value: config.radius },
        uStrength: { value: config.strength },
        uSpace: { value: config.space },
        uDisturbance: { value: config.disturbance },
        uFeather: { value: config.feather },
        uThreshold: { value: config.threshold },
        uCompensation: { value: config.compensation },
        uDispersion: { value: config.dispersion },
        uScale: { value: config.scale },
        uProgress: { value: 0 },
        uFadeIn: { value: config.fadeIn ? 1.0 : 0.0 }
    }), [texture, size])

    useFrame(() => {
        if (shaderRef.current) {
            shaderRef.current.uniforms.uProgress.value = progress
            shaderRef.current.uniforms.uMouse.value.set(mousePos.x, mousePos.y)
        }
    })

    return (
        <mesh scale={[viewport.width, viewport.height, 1]}>
            <planeGeometry />
            <shaderMaterial
                ref={shaderRef}
                vertexShader={vertexShader}
                fragmentShader={fragmentShader}
                uniforms={uniforms}
                transparent
            />
        </mesh>
    )
}

// Default configuration - ENHANCED for dramatic transition effect
const defaultConfig = {
    radius: 1.2,        // Larger radius for more visible effect
    strength: 0.8,      // Stronger distortion
    space: 0.15,        // Slightly less flat center
    disturbance: 1.0,   // More surface texture/noise
    feather: 0.6,       // Softer edge blend
    threshold: 0.4,     // Earlier feather start
    compensation: 0.4,  // More edge compensation
    dispersion: 1.2,    // Stronger chromatic aberration
    scale: 1.3,         // More zoom/magnification
    fadeIn: true,
    duration: 1.2       // Slightly faster for snappier feel
}

// Create a gradient texture as fallback/base
function createGradientTexture(width, height, color1 = '#0a0a15', color2 = '#1a1a2e') {
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')

    const gradient = ctx.createRadialGradient(
        width / 2, height / 2, 0,
        width / 2, height / 2, Math.max(width, height) * 0.7
    )
    gradient.addColorStop(0, color1)
    gradient.addColorStop(1, color2)

    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, width, height)

    return new THREE.CanvasTexture(canvas)
}

// Capture visible images and create composite
function captureScreenSimple() {
    return new Promise((resolve) => {
        const width = window.innerWidth
        const height = window.innerHeight
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const ctx = canvas.getContext('2d')

        // Fill with dark background
        ctx.fillStyle = '#0a0a0a'
        ctx.fillRect(0, 0, width, height)

        // Try to capture visible images
        const images = document.querySelectorAll('img')

        images.forEach(img => {
            if (img.complete && img.naturalWidth > 0) {
                const rect = img.getBoundingClientRect()
                if (rect.width > 50 && rect.height > 50) {
                    try {
                        ctx.drawImage(img, rect.left, rect.top, rect.width, rect.height)
                    } catch (e) {
                        // Cross-origin image, skip
                    }
                }
            }
        })

        // Add text overlay effect
        const texts = document.querySelectorAll('h1, h2, .hero-title')
        texts.forEach(el => {
            const rect = el.getBoundingClientRect()
            const style = window.getComputedStyle(el)
            ctx.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
            ctx.fillStyle = style.color || '#ffffff'
            ctx.textAlign = 'center'
            ctx.fillText(el.innerText, rect.left + rect.width / 2, rect.top + rect.height / 2)
        })

        resolve(new THREE.CanvasTexture(canvas))
    })
}

export default function MagnifierTransition({ phase, onOutComplete, onInComplete, config = {} }) {
    const [texture, setTexture] = useState(null)
    const [progress, setProgress] = useState(0)
    const [mousePos, setMousePos] = useState({ x: 0.5, y: 0.5 })
    const [isVisible, setIsVisible] = useState(false)
    const animationRef = useRef(null)
    const currentPhaseRef = useRef(null)

    const finalConfig = useMemo(() => ({ ...defaultConfig, ...config }), [config])

    // Track mouse position
    useEffect(() => {
        const handleMouseMove = (e) => {
            if (!phase) {
                setMousePos({
                    x: e.clientX / window.innerWidth,
                    y: 1.0 - e.clientY / window.innerHeight
                })
            }
        }
        window.addEventListener('mousemove', handleMouseMove)
        return () => window.removeEventListener('mousemove', handleMouseMove)
    }, [phase])

    // Handle phase changes
    useEffect(() => {
        // Cleanup previous animation
        if (animationRef.current) {
            animationRef.current.kill()
            animationRef.current = null
        }

        // Phase: OUT - expand effect (leaving current page)
        if (phase === 'out' && currentPhaseRef.current !== 'out') {
            currentPhaseRef.current = 'out'
            setIsVisible(true)
            setProgress(0)

            captureScreenSimple().then((tex) => {
                setTexture(tex)

                animationRef.current = gsap.to({ val: 0 }, {
                    val: 1.5,
                    duration: finalConfig.duration * 0.5,
                    ease: 'power2.in',
                    onUpdate: function () {
                        setProgress(this.targets()[0].val)
                    },
                    onComplete: () => {
                        onOutComplete && onOutComplete()
                    }
                })
            })
        }

        // Phase: IN - contract effect (entering new page)
        if (phase === 'in' && currentPhaseRef.current !== 'in') {
            currentPhaseRef.current = 'in'

            // Small delay to let new page render, then capture it
            setTimeout(() => {
                captureScreenSimple().then((tex) => {
                    setTexture(tex)
                    setProgress(1.5)

                    animationRef.current = gsap.to({ val: 1.5 }, {
                        val: 0,
                        duration: finalConfig.duration * 0.6,
                        ease: 'power2.out',
                        onUpdate: function () {
                            setProgress(this.targets()[0].val)
                        },
                        onComplete: () => {
                            setIsVisible(false)
                            setTexture(null)
                            setProgress(0)
                            currentPhaseRef.current = null
                            onInComplete && onInComplete()
                        }
                    })
                })
            }, 50)
        }

        // Reset when phase becomes null
        if (phase === null && currentPhaseRef.current !== null) {
            currentPhaseRef.current = null
            setIsVisible(false)
            setTexture(null)
            setProgress(0)
        }

        return () => {
            if (animationRef.current) {
                animationRef.current.kill()
            }
        }
    }, [phase, finalConfig.duration, onOutComplete, onInComplete])

    if (!isVisible || !texture) return null

    return (
        <div
            className="fixed inset-0 z-[9999] pointer-events-none"
            style={{ background: 'transparent' }}
        >
            <Canvas
                gl={{
                    antialias: true,
                    alpha: true,
                    powerPreference: 'high-performance',
                    failIfMajorPerformanceCaveat: false
                }}
                camera={{ position: [0, 0, 1] }}
                onCreated={({ gl }) => {
                    gl.setClearColor(0x000000, 0)
                }}
            >
                <MagnifierEffect
                    texture={texture}
                    progress={progress}
                    mousePos={mousePos}
                    config={finalConfig}
                />
            </Canvas>
        </div>
    )
}
