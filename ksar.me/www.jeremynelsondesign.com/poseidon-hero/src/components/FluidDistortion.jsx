import { useRef, useEffect, useMemo, Suspense } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { useTexture } from '@react-three/drei'
import * as THREE from 'three'

// ========================================
// SHADERS
// ========================================

const displayVertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const displayFragmentShader = `
uniform sampler2D uTexture;
uniform sampler2D uDisplacement;
uniform vec2 uResolution;
uniform vec2 uImageResolution;
varying vec2 vUv;

vec2 getCoverUV(vec2 uv, vec2 imageRes, vec2 canvasRes) {
    vec2 imageAspect = imageRes / min(imageRes.x, imageRes.y);
    vec2 canvasAspect = canvasRes / min(canvasRes.x, canvasRes.y);
    vec2 scale = canvasAspect / imageAspect;
    vec2 offset = (1.0 - scale) * 0.5;
    return uv * scale + offset;
}

void main() {
    vec2 uv = vUv;
    
    // Sample displacement
    vec4 disp = texture2D(uDisplacement, uv);
    
    // Apply displacement
    vec2 distortedUv = uv + disp.rg * 0.1;
    
    // Cover-fit UV
    vec2 correctUv = getCoverUV(distortedUv, uImageResolution, uResolution);
    
    // Sample texture
    vec4 color = texture2D(uTexture, correctUv);
    
    gl_FragColor = color;
}
`

const displacementVertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const displacementFragmentShader = `
uniform sampler2D uTexture;
uniform vec2 uMouse;
uniform vec2 uPrevMouse;
uniform float uAspect;
uniform float uTime;
varying vec2 vUv;

// Simple noise для турбулентности
float random(vec2 st) {
    return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}

float noise(vec2 st) {
    vec2 i = floor(st);
    vec2 f = fract(st);
    float a = random(i);
    float b = random(i + vec2(1.0, 0.0));
    float c = random(i + vec2(0.0, 1.0));
    float d = random(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

void main() {
    vec2 uv = vUv;
    vec4 color = texture2D(uTexture, uv);
    
    // Aspect-corrected coordinates
    vec2 mouse = uMouse;
    mouse.x *= uAspect;
    vec2 prevMouse = uPrevMouse;
    prevMouse.x *= uAspect;
    vec2 uvAdj = uv;
    uvAdj.x *= uAspect;
    
    // Direction
    vec2 direction = normalize(mouse - prevMouse);
    float dist = distance(uvAdj, mouse);
    
    // БОЛЬШАЯ КИСТЬ (150px)
    float brushSize = 0.25;
    float influence = smoothstep(brushSize, brushSize * 0.3, dist);
    
    // ТУРБУЛЕНТНОСТЬ
    float turbulence = noise(uv * 8.0 + uTime * 0.5) * 0.015;
    
    // Displacement
    vec2 displacement = (direction * influence * 0.35) + vec2(turbulence);
    
    // МЕДЛЕННОЕ ЗАТУХАНИЕ (0.98)
    color.rg *= 0.98;
    color.rg += displacement;
    
    gl_FragColor = color;
}
`

// ========================================
// FLUID COMPONENT
// ========================================

function FluidMaterial({ imageUrl }) {
    const { viewport, size: canvasSize, gl } = useThree()
    const texture = useTexture(imageUrl)

    const imageResolution = useMemo(() => {
        if (texture.image) {
            return new THREE.Vector2(texture.image.width, texture.image.height)
        }
        return new THREE.Vector2(1920, 1080)
    }, [texture])

    // Displacement FBOs (уменьшенное разрешение для производительности)
    const fboA = useMemo(() => new THREE.WebGLRenderTarget(
        Math.min(canvasSize.width / 3, 512),
        Math.min(canvasSize.height / 3, 512),
        {
            minFilter: THREE.LinearFilter,
            magFilter: THREE.LinearFilter,
            format: THREE.RGBAFormat,
            type: THREE.FloatType
        }
    ), [canvasSize])

    const fboB = useMemo(() => new THREE.WebGLRenderTarget(
        Math.min(canvasSize.width / 3, 512),
        Math.min(canvasSize.height / 3, 512),
        {
            minFilter: THREE.LinearFilter,
            magFilter: THREE.LinearFilter,
            format: THREE.RGBAFormat,
            type: THREE.FloatType
        }
    ), [canvasSize])

    const displScene = useMemo(() => new THREE.Scene(), [])
    const displCamera = useMemo(() => new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1), [])

    const mouse = useRef(new THREE.Vector2(0.5, 0.5))
    const prevMouse = useRef(new THREE.Vector2(0.5, 0.5))
    const currentFBO = useRef(fboA)
    const prevFBO = useRef(fboB)

    const displMaterial = useRef()
    const displayMaterial = useRef()

    // Mouse tracking
    useEffect(() => {
        const updateMouse = (x, y) => {
            prevMouse.current.copy(mouse.current)
            mouse.current.set(
                x / window.innerWidth,
                1.0 - y / window.innerHeight
            )
        }

        const onMouseMove = (e) => updateMouse(e.clientX, e.clientY)
        const onTouchMove = (e) => {
            if (e.touches.length > 0) {
                updateMouse(e.touches[0].clientX, e.touches[0].clientY)
            }
        }

        window.addEventListener('mousemove', onMouseMove)
        window.addEventListener('touchmove', onTouchMove, { passive: true })

        return () => {
            window.removeEventListener('mousemove', onMouseMove)
            window.removeEventListener('touchmove', onTouchMove)
        }
    }, [])

    // Displacement scene setup
    useEffect(() => {
        const geom = new THREE.PlaneGeometry(2, 2)
        const mat = new THREE.ShaderMaterial({
            vertexShader: displacementVertexShader,
            fragmentShader: displacementFragmentShader,
            uniforms: {
                uTexture: { value: null },
                uMouse: { value: mouse.current },
                uPrevMouse: { value: prevMouse.current },
                uAspect: { value: 1 },
                uTime: { value: 0 }
            }
        })
        displMaterial.current = mat
        const mesh = new THREE.Mesh(geom, mat)
        displScene.add(mesh)

        return () => {
            geom.dispose()
            mat.dispose()
        }
    }, [displScene])

    useFrame((state) => {
        if (!displMaterial.current || !displayMaterial.current) return

        // Update displacement
        displMaterial.current.uniforms.uTexture.value = prevFBO.current.texture
        displMaterial.current.uniforms.uMouse.value = mouse.current
        displMaterial.current.uniforms.uPrevMouse.value = prevMouse.current
        displMaterial.current.uniforms.uAspect.value = canvasSize.width / canvasSize.height
        displMaterial.current.uniforms.uTime.value = state.clock.elapsedTime

        gl.setRenderTarget(currentFBO.current)
        gl.render(displScene, displCamera)
        gl.setRenderTarget(null)

        // Update display
        displayMaterial.current.uniforms.uDisplacement.value = currentFBO.current.texture

        // Swap
        const temp = currentFBO.current
        currentFBO.current = prevFBO.current
        prevFBO.current = temp
    })

    // Cleanup
    useEffect(() => {
        return () => {
            fboA.dispose()
            fboB.dispose()
        }
    }, [fboA, fboB])

    return (
        <mesh scale={[viewport.width, viewport.height, 1]}>
            <planeGeometry />
            <shaderMaterial
                ref={displayMaterial}
                vertexShader={displayVertexShader}
                fragmentShader={displayFragmentShader}
                uniforms={{
                    uTexture: { value: texture },
                    uDisplacement: { value: null },
                    uResolution: { value: new THREE.Vector2(canvasSize.width, canvasSize.height) },
                    uImageResolution: { value: imageResolution }
                }}
            />
        </mesh>
    )
}

// ========================================
// MAIN EXPORT
// ========================================

export default function FluidDistortion({ imageUrl }) {
    return (
        <div className="absolute inset-0 w-full h-full bg-black">
            <Canvas>
                <Suspense fallback={null}>
                    <FluidMaterial imageUrl={imageUrl} />
                </Suspense>
            </Canvas>
        </div>
    )
}
