import React, { useRef, useEffect, useMemo, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import gsap from 'gsap'

/**
 * Vortex Effect with Warp/Zoom/Lag
 * 
 * - Zoom In: Image starts small (50%) and grows to 100%
 * - Lagging Trails: Distortion trails lag heavily behind the opening circle
 * - Spiral/Rainbow Trails: Chromatic aberration increases at edges
 */

const fragmentShader = `
precision highp float;

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uProgress;
uniform float uTime;
uniform float uRadius;
uniform float uChromaticStrength;
uniform float uFeather;
uniform vec2 uCenter;

varying vec2 vUv;

#define PI 3.14159265359

// Rotate a 2D vector by angle
vec2 rotate2D(vec2 v, float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return vec2(v.x * c - v.y * s, v.x * s + v.y * c);
}

void main() {
    vec2 uv = vUv;
    
    // === ZOOM IN EFFECT ===
    // During opening: image zooms IN (gets bigger/closer)
    float zoomStart = 0.5;   // Starts very small (50% size)
    float zoomEnd = 1.0;     // Ends at normal size
    float currentZoom = mix(zoomStart, zoomEnd, uProgress);
    
    // Apply zoom by scaling UV from center
    vec2 zoomedUV = (uv - 0.5) * currentZoom + 0.5;
    
    // Aspect ratio correction for proper circle
    float aspect = uResolution.x / uResolution.y;
    vec2 center = uCenter;
    
    // Calculate distance from center with aspect correction
    vec2 uvCorrected = uv;
    uvCorrected.x = (uvCorrected.x - 0.5) * aspect + 0.5;
    vec2 centerCorrected = center;
    centerCorrected.x = (centerCorrected.x - 0.5) * aspect + 0.5;
    
    float dist = length(uvCorrected - centerCorrected);
    
    // Maximum radius to cover the entire screen
    float maxRadius = length(vec2(aspect * 0.5, 0.5));
    
    // Feather/stretch zone width - wider for softer edge
    float stretchZone = uFeather * 0.4;
    
    // Current animated radius (main circle - moves FAST)
    // Faster start with power 0.7
    float fastProgress = pow(uProgress, 0.7);
    float startRadius = -stretchZone * 0.5;
    float endRadius = maxRadius + stretchZone * 0.5;
    float currentRadius = mix(startRadius, endRadius, fastProgress);
    
    // LAGGING radius for distortions (moves SLOWER than circle)
    // Even slower trail with power 4.0
    float lagAmount = 0.5; 
    float lagProgress = pow(uProgress, 4.0); 
    float laggingRadius = mix(startRadius, endRadius, lagProgress);
    
    // Direction from center (for stretching)
    vec2 dir = normalize(uv - center + vec2(0.0001));
    
    // === STRETCHING EFFECT ===
    // Trails stretch toward the LAGGING radius (which is behind the main circle)
    float stretchAmount = 0.0;
    vec2 stretchedUV = zoomedUV;
    
    // Zone between lagging radius and current radius = active trail zone
    float trailZone = currentRadius - laggingRadius;
    
    if (dist > laggingRadius && dist < currentRadius + stretchZone * 3.0) {
        float outsideDist = dist - laggingRadius;
        
        // Lower decay value (0.8) makes trails LONGER
        float stretchFactor = 1.0 - exp(-outsideDist / max(trailZone, 0.01) * 0.8);
        stretchAmount = stretchFactor;
        
        // Pull toward lagging edge point (not current edge)
        vec2 edgePoint = center + dir * laggingRadius / aspect;
        edgePoint.x = center.x + (edgePoint.x - center.x) / aspect;
        
        // Strong stretch pull
        stretchedUV = mix(zoomedUV, edgePoint, stretchFactor * 0.9);
    }
    
    // === EFFECT STARTUP DELAY ===
    // No distortion for first 5% of opening, then gradually fade in
    float effectStartup = smoothstep(0.03, 0.08, uProgress);
    stretchAmount *= effectStartup;
    
    // === CHROMATIC ABERRATION ===
    // Strength increases gradually as image opens AND away from center
    float abberationRamp = smoothstep(0.0, 0.8, uProgress);
    
    // Radial boost: 0% strength at center, 90% at edges (approx 0.5 radius)
    float radialBoost = mix(0.0, 0.9, smoothstep(0.0, 0.6, dist));
    
    float chromaticAmount = uChromaticStrength * stretchAmount * 0.03 * abberationRamp * effectStartup * radialBoost;
    
    vec2 redUV = stretchedUV + dir * chromaticAmount * 1.0;
    vec2 greenUV = stretchedUV + dir * chromaticAmount * 0.4;
    vec2 blueUV = stretchedUV - dir * chromaticAmount * 0.5;
    
    float r = texture2D(uTexture, redUV).r;
    float g = texture2D(uTexture, greenUV).g;
    float b = texture2D(uTexture, blueUV).b;
    
    vec3 color = vec3(r, g, b);
    
    // === FADE OUT ===
    // Use lagging radius for proper trail fadeout
    float fadeDist = dist - laggingRadius;
    float fadeOut = 1.0 - smoothstep(0.0, stretchZone * 2.0, fadeDist);
    
    color *= fadeOut;
    
    // Inside lagging circle - smooth transition to normal static image
    // Very wide transition zone for invisible boundary
    float insideMask = smoothstep(laggingRadius + stretchZone * 0.2, laggingRadius - stretchZone * 1.5, dist);
    vec3 normalColor = texture2D(uTexture, zoomedUV).rgb;
    color = mix(color, normalColor, insideMask);
    
    // Black outside - use lagging radius
    float totalMask = smoothstep(laggingRadius + stretchZone * 2.5, laggingRadius, dist);
    color *= totalMask;
    
    // Hard cutoff when fully closed
    if (laggingRadius < -stretchZone * 0.3) {
        color = vec3(0.0);
    }
    
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

function VortexMesh({ texture, config }) {
    const { size, viewport } = useThree()
    const materialRef = useRef()
    const timeRef = useRef(0)
    const progressRef = useRef(0)
    const isAnimatingRef = useRef(false)

    const uniforms = useMemo(() => ({
        uTexture: { value: texture },
        uResolution: { value: new THREE.Vector2(size.width, size.height) },
        uProgress: { value: 0 },
        uTime: { value: 0 },
        uRadius: { value: config.radius },
        uChromaticStrength: { value: config.chromaticStrength },
        uFeather: { value: config.feather },
        uCenter: { value: new THREE.Vector2(0.5, 0.5) }
    }), [texture, size])

    // Animation cycle
    useEffect(() => {
        const runAnimation = () => {
            if (isAnimatingRef.current) return
            isAnimatingRef.current = true
            progressRef.current = 0

            // Expand animation - from 0 to 1
            gsap.to(progressRef, {
                current: 1,
                duration: config.duration,
                ease: config.easing || 'power2.out',
                delay: config.initialDelay,
                onComplete: () => {
                    // Hold at full reveal
                    setTimeout(() => {
                        if (config.reverseOnComplete) {
                            // Reverse animation
                            gsap.to(progressRef, {
                                current: 0,
                                duration: config.reverseDuration || config.duration,
                                ease: 'power2.in',
                                onComplete: () => {
                                    isAnimatingRef.current = false
                                    if (config.loop) {
                                        setTimeout(runAnimation, config.loopDelay * 1000)
                                    }
                                }
                            })
                        } else {
                            isAnimatingRef.current = false
                            if (config.loop) {
                                // Reset and loop
                                progressRef.current = 0
                                setTimeout(runAnimation, config.loopDelay * 1000)
                            }
                        }
                    }, (config.holdDuration || 0) * 1000)
                }
            })
        }

        if (config.autoPlay) {
            runAnimation()
        }

        return () => {
            gsap.killTweensOf(progressRef)
        }
    }, [config])

    // Manual trigger
    useEffect(() => {
        window.triggerVortex = () => {
            if (isAnimatingRef.current) return
            isAnimatingRef.current = true
            progressRef.current = 0

            gsap.to(progressRef, {
                current: 1,
                duration: config.duration,
                ease: config.easing || 'power2.out',
                onComplete: () => {
                    setTimeout(() => {
                        if (config.reverseOnComplete) {
                            gsap.to(progressRef, {
                                current: 0,
                                duration: config.reverseDuration || config.duration,
                                ease: 'power2.in',
                                onComplete: () => {
                                    isAnimatingRef.current = false
                                }
                            })
                        } else {
                            isAnimatingRef.current = false
                        }
                    }, (config.holdDuration || 0) * 1000)
                }
            })
        }

        return () => {
            delete window.triggerVortex
        }
    }, [config])

    useFrame((state, delta) => {
        if (!materialRef.current) return

        timeRef.current += delta

        const u = materialRef.current.uniforms
        u.uProgress.value = progressRef.current
        u.uTime.value = timeRef.current
        u.uResolution.value.set(size.width, size.height)
        u.uRadius.value = config.radius
        u.uChromaticStrength.value = config.chromaticStrength
        u.uFeather.value = config.feather
    })

    return (
        <mesh scale={[viewport.width, viewport.height, 1]}>
            <planeGeometry args={[1, 1]} />
            <shaderMaterial
                ref={materialRef}
                vertexShader={vertexShader}
                fragmentShader={fragmentShader}
                uniforms={uniforms}
                transparent={true}
            />
        </mesh>
    )
}

// Default configuration
const defaultConfig = {
    radius: 1.0,                  // Max radius multiplier
    chromaticStrength: 5.0,       // RGB split intensity (base)
    feather: 0.5,                 // Edge softness
    duration: 2.3,                // Opening duration
    reverseDuration: 1.3,         // Closing duration
    holdDuration: 2.0,            // Hold at full reveal
    initialDelay: 0.5,            // Delay before animation starts
    autoPlay: true,               // Start automatically
    loop: true,                   // Loop the animation
    loopDelay: 1.0,               // Delay between loops
    reverseOnComplete: true,      // Shrink back after reveal
    easing: 'power2.out'          // Easing function
}

export default function VortexEffect({
    imageSrc = '/Vortex_example.mp4', // Default to video or image
    config = {},
    className = '',
    style = {}
}) {
    const containerRef = useRef(null)
    const [texture, setTexture] = useState(null)
    const [isLoaded, setIsLoaded] = useState(false)

    const finalConfig = useMemo(() => ({ ...defaultConfig, ...config }), [config])

    // Load texture
    useEffect(() => {
        console.log('Loading texture:', imageSrc)
        const loader = new THREE.TextureLoader()
        loader.load(
            imageSrc,
            (tex) => {
                console.log('Texture loaded successfully')
                tex.minFilter = THREE.LinearFilter
                tex.magFilter = THREE.LinearFilter
                tex.wrapS = THREE.ClampToEdgeWrapping
                tex.wrapT = THREE.ClampToEdgeWrapping
                setTexture(tex)
                setIsLoaded(true)
            },
            undefined,
            (err) => {
                console.error('Error loading texture:', err)
            }
        )
    }, [imageSrc])

    return (
        <div
            ref={containerRef}
            className={`vortex-effect-container ${className}`}
            style={{
                width: '100%',
                height: '100%',
                position: 'relative',
                overflow: 'hidden',
                background: '#000',
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
                    <VortexMesh
                        texture={texture}
                        config={finalConfig}
                    />
                </Canvas>
            )}

            {!isLoaded && (
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: '#000'
                }}>
                    <div style={{
                        width: 40,
                        height: 40,
                        border: '3px solid rgba(255,255,255,0.1)',
                        borderTopColor: '#00d4ff',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite'
                    }} />
                </div>
            )}
        </div>
    )
}
