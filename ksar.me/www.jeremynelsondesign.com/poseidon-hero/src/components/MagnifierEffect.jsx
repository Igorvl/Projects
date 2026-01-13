import React, { useRef, useEffect, useMemo, useCallback, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import gsap from 'gsap'

/**
 * Magnifier+ Liquid Distortion Effect
 * Based on Reveals.cool Magnifier component
 * 
 * Properties:
 * - radius: Magnifier radius (ratio of canvas wider side) 0-1
 * - strength: Distortion intensity 0-1
 * - space: Center flatness range 0-1
 * - disturbance: Surface irregular texture intensity 0-1
 * - feather: Edge feathering intensity 0-1
 * - threshold: Feathering starting point 0-1
 * - compensation: Feathering extension range 0-1
 * - dispersion: Edge chromatic dispersion 0-1
 * - scale: Content zoom 0-1
 * - fadeIn: Fade-in effect on start
 * - sequence: Animation sequence mode
 */

const fragmentShader = `
precision highp float;

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform vec2 uMouse;
uniform vec2 uTargetMouse;
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
uniform float uTime;

varying vec2 vUv;

// Simplex noise functions for organic disturbance
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

float snoise(vec2 v) {
    const vec4 C = vec4(0.211324865405187, 0.366025403784439,
                        -0.577350269189626, 0.024390243902439);
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v - i + dot(i, C.xx);
    vec2 i1;
    i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;
    i = mod289(i);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
                     + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy),
                            dot(x12.zw,x12.zw)), 0.0);
    m = m*m;
    m = m*m;
    vec3 x = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x) - 0.5;
    vec3 ox = floor(x + 0.5);
    vec3 a0 = x - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
    vec3 g;
    g.x = a0.x * x0.x + h.x * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return 130.0 * dot(m, g);
}

// Fractal Brownian Motion for richer noise
float fbm(vec2 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 4; i++) {
        f += w * snoise(p);
        p *= 2.0;
        w *= 0.5;
    }
    return f;
}

void main() {
    vec2 uv = vUv;
    
    // Aspect ratio correction
    float aspect = uResolution.x / uResolution.y;
    vec2 uvAspect = uv;
    uvAspect.x *= aspect;
    
    vec2 mouseAspect = uMouse;
    mouseAspect.x *= aspect;
    
    // Distance from mouse position
    float dist = distance(uvAspect, mouseAspect);
    
    // Animated radius based on progress
    float maxRadius = uRadius * max(aspect, 1.0);
    float currentRadius = maxRadius * uProgress;
    
    // Feathering calculation - smooth edge transition
    float featherStart = currentRadius * uThreshold;
    float featherEnd = currentRadius * (1.0 + uCompensation);
    float mask = 1.0 - smoothstep(featherStart, featherEnd, dist);
    mask = pow(mask, uFeather * 2.0 + 0.1);
    
    // Space (center flatness) - creates flat center like optical lens
    float spaceRadius = currentRadius * uSpace;
    float spaceMask = smoothstep(0.0, spaceRadius, dist);
    
    // Organic disturbance using fractal noise
    float noise1 = fbm(uv * 8.0 + uTime * 0.3);
    float noise2 = fbm(uv * 16.0 - uTime * 0.2);
    float disturbNoise = noise1 * 0.7 + noise2 * 0.3;
    float disturbance = disturbNoise * uDisturbance * mask * spaceMask * 0.04;
    
    // Direction from mouse to current pixel
    vec2 dir = normalize(uv - uMouse + 0.0001);
    
    // Magnification/Scale effect - zoom into center
    float magnification = 1.0 + (uScale * 0.5) * mask * (1.0 - spaceMask * 0.5);
    
    // Liquid distortion strength
    float distortAmount = uStrength * mask * spaceMask;
    
    // Calculate distorted UV with lens-like magnification
    vec2 distortedUv = uMouse + (uv - uMouse) / magnification;
    
    // Add organic wave-like distortion (liquid ripples)
    float wave = sin(dist * 20.0 - uTime * 2.0) * 0.5 + 0.5;
    float wave2 = sin(dist * 35.0 + uTime * 1.5) * 0.3;
    distortedUv += dir * distortAmount * (wave * 0.08 + wave2 * 0.04);
    
    // Add disturbance noise to UV
    distortedUv += dir * disturbance;
    
    // Chromatic dispersion at edges (rainbow edge effect)
    float dispersionAmount = uDispersion * mask * (1.0 - spaceMask) * 0.02;
    
    vec2 redOffset = distortedUv + dir * dispersionAmount * 1.2;
    vec2 greenOffset = distortedUv;
    vec2 blueOffset = distortedUv - dir * dispersionAmount * 1.2;
    
    // Sample texture with chromatic aberration
    float r = texture2D(uTexture, redOffset).r;
    float g = texture2D(uTexture, greenOffset).g;
    float b = texture2D(uTexture, blueOffset).b;
    
    vec3 color = vec3(r, g, b);
    
    // Subtle brightness boost in center
    float centerBrightness = 1.0 + mask * (1.0 - spaceMask) * 0.15;
    color *= centerBrightness;
    
    // Subtle vignette inside magnifier for optical depth
    float vignette = 1.0 - mask * 0.08;
    color *= vignette;
    
    gl_FragColor = vec4(color, 1.0);
}
`

const vertexShader = `
varying vec2 vUv;
void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

function MagnifierShaderMesh({ texture, config, mouseRef }) {
    const { size, viewport } = useThree()
    const materialRef = useRef()
    const targetMouseRef = useRef({ x: 0.5, y: 0.5 })
    const currentMouseRef = useRef({ x: 0.5, y: 0.5 })
    const timeRef = useRef(0)
    const progressRef = useRef(0)

    const uniforms = useMemo(() => ({
        uTexture: { value: texture },
        uResolution: { value: new THREE.Vector2(size.width, size.height) },
        uMouse: { value: new THREE.Vector2(0.5, 0.5) },
        uTargetMouse: { value: new THREE.Vector2(0.5, 0.5) },
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
        uTime: { value: 0 }
    }), [texture, size, config])

    // Animate progress on mount - with optional fadeOut
    useEffect(() => {
        // Start at full strength
        progressRef.current = 1

        const fadeOutDelay = config.fadeOutDelay || 0

        // If fadeIn is enabled, animate in first
        if (config.fadeIn) {
            progressRef.current = 0
            gsap.to(progressRef, {
                current: 1,
                duration: 1.2,
                ease: 'power2.out',
                onComplete: () => {
                    // Then fade out if fadeOutDuration is set
                    if (config.fadeOutDuration && config.fadeOutDuration > 0) {
                        gsap.to(progressRef, {
                            current: 0,
                            duration: config.fadeOutDuration,
                            ease: 'power2.inOut',
                            delay: fadeOutDelay
                        })
                    }
                }
            })
        } else if (config.fadeOutDuration && config.fadeOutDuration > 0) {
            // No fadeIn, just fade out over time with delay
            gsap.to(progressRef, {
                current: 0,
                duration: config.fadeOutDuration,
                ease: 'power2.inOut',
                delay: fadeOutDelay
            })
        }
    }, [config.fadeIn, config.fadeOutDuration, config.fadeOutDelay])

    // Update on each frame
    useFrame((state, delta) => {
        if (!materialRef.current) return

        timeRef.current += delta

        // Smooth mouse interpolation (liquid-like following)
        const lerpFactor = config.sequence ? 0.03 : 0.08
        currentMouseRef.current.x += (mouseRef.current.x - currentMouseRef.current.x) * lerpFactor
        currentMouseRef.current.y += (mouseRef.current.y - currentMouseRef.current.y) * lerpFactor

        // Update all uniforms (for real-time slider control)
        const u = materialRef.current.uniforms
        u.uMouse.value.set(currentMouseRef.current.x, currentMouseRef.current.y)
        u.uProgress.value = progressRef.current
        u.uTime.value = timeRef.current
        u.uResolution.value.set(size.width, size.height)

        // Update config uniforms dynamically
        u.uRadius.value = config.radius
        u.uStrength.value = config.strength
        u.uSpace.value = config.space
        u.uDisturbance.value = config.disturbance
        u.uFeather.value = config.feather
        u.uThreshold.value = config.threshold
        u.uCompensation.value = config.compensation
        u.uDispersion.value = config.dispersion
        u.uScale.value = config.scale
    })

    return (
        <mesh scale={[viewport.width, viewport.height, 1]}>
            <planeGeometry args={[1, 1]} />
            <shaderMaterial
                ref={materialRef}
                vertexShader={vertexShader}
                fragmentShader={fragmentShader}
                uniforms={uniforms}
            />
        </mesh>
    )
}

// Default configuration matching Reveals.cool Magnifier+
const defaultConfig = {
    radius: 0.35,        // Magnifier radius (0-1, ratio of wider side)
    strength: 0.45,      // Distortion intensity (0-1)
    space: 0.25,         // Center flatness range (0-1)
    disturbance: 0.6,    // Surface irregular texture (0-1)
    feather: 0.5,        // Edge feathering intensity (0-1)
    threshold: 0.3,      // Feathering starting point (0-1)
    compensation: 0.5,   // Feathering extension range (0-1)
    dispersion: 0.7,     // Edge chromatic dispersion (0-1)
    scale: 0.3,          // Content zoom (0-1)
    fadeIn: true,        // Fade-in effect
    sequence: true       // Sequence mode - slower, more liquid following
}

export default function MagnifierEffect({
    imageSrc = '/triptix.jpg',
    config = {},
    followCursor = true,
    className = '',
    style = {}
}) {
    const containerRef = useRef(null)
    const mouseRef = useRef({ x: 0.5, y: 0.5 })
    const [texture, setTexture] = useState(null)
    const [isLoaded, setIsLoaded] = useState(false)

    const finalConfig = useMemo(() => ({ ...defaultConfig, ...config }), [config])

    // Load texture
    useEffect(() => {
        const loader = new THREE.TextureLoader()
        loader.load(imageSrc, (tex) => {
            tex.minFilter = THREE.LinearFilter
            tex.magFilter = THREE.LinearFilter
            tex.wrapS = THREE.ClampToEdgeWrapping
            tex.wrapT = THREE.ClampToEdgeWrapping
            setTexture(tex)
            setIsLoaded(true)
        })
    }, [imageSrc])

    // Track mouse position (only if followCursor is enabled)
    useEffect(() => {
        if (!followCursor) {
            // Fixed center position
            mouseRef.current = { x: 0.5, y: 0.5 }
            return
        }

        const handleMouseMove = (e) => {
            if (!containerRef.current) return

            const rect = containerRef.current.getBoundingClientRect()
            mouseRef.current = {
                x: (e.clientX - rect.left) / rect.width,
                y: 1.0 - (e.clientY - rect.top) / rect.height
            }
        }

        window.addEventListener('mousemove', handleMouseMove)
        return () => window.removeEventListener('mousemove', handleMouseMove)
    }, [followCursor])

    return (
        <div
            ref={containerRef}
            className={`magnifier-effect-container ${className}`}
            style={{
                width: '100%',
                height: '100%',
                position: 'relative',
                overflow: 'hidden',
                ...style
            }}
        >
            {isLoaded && texture && (
                <Canvas
                    gl={{
                        antialias: true,
                        alpha: false,
                        powerPreference: 'high-performance'
                    }}
                    camera={{ position: [0, 0, 1] }}
                    style={{ width: '100%', height: '100%' }}
                >
                    <MagnifierShaderMesh
                        texture={texture}
                        config={finalConfig}
                        mouseRef={mouseRef}
                    />
                </Canvas>
            )}

            {/* Loading state */}
            {!isLoaded && (
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: '#0a0a0a'
                }}>
                    <div style={{
                        width: 40,
                        height: 40,
                        border: '3px solid rgba(255,255,255,0.1)',
                        borderTopColor: '#4D9FFF',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite'
                    }} />
                </div>
            )}
        </div>
    )
}
