import React, { useRef, Suspense, useMemo } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import {
    Float,
    Text,
    Environment,
    MeshTransmissionMaterial,
    Edges
} from '@react-three/drei'
import * as THREE from 'three'

/**
 * Prismatic edge shader for rainbow refraction on crystal edges
 */
const PrismaticEdgesMaterial = {
    uniforms: {
        time: { value: 0 },
        edgeColor: { value: new THREE.Color('#ffffff') }
    },
    vertexShader: `
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        varying vec2 vUv;
        
        void main() {
            vNormal = normalize(normalMatrix * normal);
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            vViewPosition = -mvPosition.xyz;
            vUv = uv;
            gl_Position = projectionMatrix * mvPosition;
        }
    `,
    fragmentShader: `
        uniform float time;
        uniform vec3 edgeColor;
        
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        varying vec2 vUv;
        
        vec3 rainbow(float t) {
            vec3 c = 0.5 + 0.5 * cos(6.28318 * (t + vec3(0.0, 0.33, 0.67)));
            return c;
        }
        
        void main() {
            vec3 viewDir = normalize(vViewPosition);
            float fresnel = pow(1.0 - abs(dot(viewDir, vNormal)), 3.0);
            
            // Rainbow based on view angle
            float hue = dot(vNormal, vec3(1.0, 0.5, 0.3)) * 0.5 + 0.5;
            hue += time * 0.1;
            vec3 rainbow_color = rainbow(hue);
            
            vec3 finalColor = mix(edgeColor, rainbow_color, fresnel * 0.8);
            float alpha = fresnel * 0.6;
            
            gl_FragColor = vec4(finalColor, alpha);
        }
    `
}

/**
 * Main Crystal with clean glass + prismatic edges
 */
function ElementzCrystalMesh() {
    const crystalRef = useRef()
    const edgesRef = useRef()
    const prismRef = useRef()

    // Create prismatic material
    const prismMaterial = useMemo(() => {
        return new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                edgeColor: { value: new THREE.Color('#ffffff') }
            },
            vertexShader: PrismaticEdgesMaterial.vertexShader,
            fragmentShader: PrismaticEdgesMaterial.fragmentShader,
            transparent: true,
            blending: THREE.AdditiveBlending,
            side: THREE.DoubleSide,
            depthWrite: false
        })
    }, [])

    useFrame((state, delta) => {
        if (crystalRef.current) {
            // Slow, elegant rotation
            crystalRef.current.rotation.y -= delta * 0.15
            crystalRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.2) * 0.08
        }
        // Update shader time
        if (prismMaterial) {
            prismMaterial.uniforms.time.value = state.clock.elapsedTime
        }
    })

    return (
        <Float
            speed={1.2}
            rotationIntensity={0.2}
            floatIntensity={0.3}
        >
            <group ref={crystalRef} scale={[1, 1.5, 1]}>

                {/* LAYER 1: CLEAN TRANSPARENT GLASS */}
                <mesh>
                    <octahedronGeometry args={[1.8, 0]} />
                    <MeshTransmissionMaterial
                        // Maximum transparency
                        transmission={1}
                        thickness={0.1}
                        roughness={0}

                        // Very subtle chromatic aberration
                        chromaticAberration={0.02}

                        // Minimal distortion for clean text visibility
                        anisotropicBlur={0}
                        distortion={0}
                        temporalDistortion={0}

                        // Standard glass IOR
                        ior={1.5}

                        // Backside for proper glass
                        backside={true}
                        backsideThickness={0.05}

                        // Clear glass
                        color="#ffffff"

                        // Subtle reflections
                        envMapIntensity={0.3}

                        // High quality
                        samples={16}
                        resolution={2048}
                        backsideResolution={1024}
                    />
                </mesh>

                {/* LAYER 2: PRISMATIC RAINBOW SHELL */}
                {/* Slightly larger shell with rainbow refraction effect */}
                <mesh scale={[1.02, 1.02, 1.02]} ref={prismRef} material={prismMaterial}>
                    <octahedronGeometry args={[1.8, 0]} />
                </mesh>

                {/* LAYER 3: SHARP WHITE EDGES */}
                <mesh scale={[1.01, 1.01, 1.01]}>
                    <octahedronGeometry args={[1.8, 0]} />
                    <meshBasicMaterial
                        wireframe
                        color="#ffffff"
                        transparent
                        opacity={0.35}
                        blending={THREE.AdditiveBlending}
                        depthWrite={false}
                    />
                </mesh>

                {/* LAYER 4: SUBTLE INNER REFLECTIONS */}
                <mesh scale={[0.99, 0.99, 0.99]}>
                    <octahedronGeometry args={[1.8, 0]} />
                    <meshPhysicalMaterial
                        transparent
                        opacity={0.05}
                        metalness={1}
                        roughness={0}
                        envMapIntensity={2}
                        side={THREE.BackSide}
                        depthWrite={false}
                    />
                </mesh>

            </group>
        </Float>
    )
}

/**
 * High contrast studio lighting
 */
function StudioEnvironment() {
    return (
        <Environment resolution={256} background={false}>
            <group>
                {/* Key light - top right */}
                <mesh position={[8, 10, 5]} scale={[12, 12, 1]}>
                    <planeGeometry />
                    <meshBasicMaterial color="#ffffff" toneMapped={false} />
                </mesh>

                {/* Fill - left side, cool */}
                <mesh position={[-12, 0, 3]} scale={[8, 20, 1]}>
                    <planeGeometry />
                    <meshBasicMaterial color="#aaddff" toneMapped={false} />
                </mesh>

                {/* Rim - behind right, warm */}
                <mesh position={[6, -2, -10]} scale={[8, 15, 1]}>
                    <planeGeometry />
                    <meshBasicMaterial color="#ffbb77" toneMapped={false} />
                </mesh>

                {/* Top soft fill */}
                <mesh position={[0, 15, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[25, 25, 1]}>
                    <planeGeometry />
                    <meshBasicMaterial color="#ffffff" toneMapped={false} />
                </mesh>
            </group>
        </Environment>
    )
}

/**
 * Background text - ELEMENTZ
 */
function BrandText() {
    return (
        <>
            {/* Main ELEMENTZ text - behind crystal */}
            <Text
                position={[0, 0, -5]}
                fontSize={4.8}
                color="#ffffff"
                font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hjp-Ek-_EeA.woff"
                anchorX="center"
                anchorY="middle"
                fillOpacity={1}
                fontWeight={900}
                letterSpacing={-0.05}
            >
                ELEMENTZ
            </Text>

            {/* Product info - left */}
            <Text
                position={[-3.8, -2.0, -2]}
                fontSize={0.16}
                color="#777777"
                font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hjp-Ek-_EeA.woff"
                anchorX="left"
                anchorY="middle"
                lineHeight={1.6}
            >
                {`200mg CBD per serving\nspectrum    hemp\nL-theanine and reishi\nMade in California`}
            </Text>

            {/* CBD badge - right */}
            <group position={[3.4, -0.6, -1.5]}>
                <Text
                    fontSize={0.38}
                    color="#ffffff"
                    font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hjp-Ek-_EeA.woff"
                    anchorX="center"
                    anchorY="middle"
                    fontWeight={700}
                    lineHeight={1.1}
                >
                    {`WITH\nCBD`}
                </Text>
            </group>
        </>
    )
}

/**
 * Loader fallback
 */
function Loader() {
    return (
        <mesh>
            <octahedronGeometry args={[1.5, 0]} />
            <meshBasicMaterial color="#222" wireframe />
        </mesh>
    )
}

/**
 * Main Component
 */
export default function ElementzCrystal() {
    return (
        <div
            style={{
                width: '100vw',
                height: '100vh',
                background: '#000000',
                position: 'relative'
            }}
        >
            <Canvas
                camera={{
                    position: [0, 0, 8],
                    fov: 35,
                    near: 0.1,
                    far: 100
                }}
                dpr={[1, 2]}
                gl={{
                    antialias: true,
                    alpha: false,
                    powerPreference: 'high-performance'
                }}
            >
                <color attach="background" args={['#000000']} />

                {/* Minimal ambient */}
                <ambientLight intensity={0.05} />

                {/* Directional lights for edge highlights */}
                <directionalLight position={[5, 5, 5]} intensity={0.4} color="#ffffff" />
                <directionalLight position={[-5, 3, -3]} intensity={0.2} color="#88ccff" />
                <pointLight position={[0, 8, 3]} intensity={0.3} color="#ffffff" />

                <Suspense fallback={<Loader />}>
                    <StudioEnvironment />
                    <BrandText />
                    <ElementzCrystalMesh />
                </Suspense>

            </Canvas>

            {/* UI Overlay */}
            <div
                style={{
                    position: 'absolute',
                    top: '2rem',
                    left: '2rem',
                    zIndex: 10,
                    mixBlendMode: 'difference'
                }}
            >
                <a
                    href="/"
                    style={{
                        color: 'white',
                        fontSize: '0.875rem',
                        letterSpacing: '0.2em',
                        fontWeight: 500,
                        textDecoration: 'none',
                        opacity: 0.8,
                        transition: 'opacity 0.3s'
                    }}
                    onMouseEnter={(e) => e.target.style.opacity = 0.5}
                    onMouseLeave={(e) => e.target.style.opacity = 0.8}
                >
                    ← BACK TO HOME
                </a>
                <p
                    style={{
                        color: '#666',
                        fontSize: '0.75rem',
                        letterSpacing: '0.15em',
                        marginTop: '0.5rem',
                        textTransform: 'uppercase'
                    }}
                >
                    Crystal Refraction Study v3.0
                </p>
            </div>
        </div>
    )
}
