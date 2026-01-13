import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree, createPortal } from '@react-three/fiber'
import { useTexture, useFBO, useAspect, Text } from '@react-three/drei'
import * as THREE from 'three'

// --------------------------------------------------------
// SIMULATION SHADER (Flowmap - рисует след от мыши)
// --------------------------------------------------------
const simVertex = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const simFragment = `
uniform sampler2D uTexture;
uniform vec2 uMouse;
uniform float uAspect;
uniform float uVelo;
uniform float uTime;
varying vec2 vUv;

// Simple 2D noise for turbulence
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
    return mix(a, b, u.x) + (c - a)* u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
}

void main() {
  vec2 uv = vUv;
  vec2 cursor = vUv - uMouse;
  cursor.x *= uAspect;
  
  // БОЛЬШАЯ КИСТЬ (150px ~ 0.15-0.2 в нормализованных координатах)
  float brushSize = 0.18;
  float amp = 1.0 - smoothstep(0.0, brushSize, length(cursor));
  
  // ТУРБУЛЕНТНОСТЬ
  float turbulence = noise(uv * 5.0 + uTime * 0.3) * 0.02;
  
  vec4 old = texture2D(uTexture, uv);
  
  // МЕДЛЕННОЕ ЗАТУХАНИЕ (0.97 = очень медленно исчезает, как круги на воде)
  vec4 newColor = old * 0.97;
  
  // Добавляем след от курсора с турбулентностью
  newColor.r += (amp * uVelo * 3.0) + turbulence;
  
  gl_FragColor = clamp(newColor, 0.0, 1.0);
}
`

// --------------------------------------------------------
// DISPLAY SHADER (Применяет искажение к контенту)
// --------------------------------------------------------
const dispVertex = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const dispFragment = `
uniform sampler2D uTexture;
uniform sampler2D uDisplacement;
uniform float uAberration;
varying vec2 vUv;

void main() {
  vec2 uv = vUv;
  
  // Читаем интенсивность из flowmap
  float disp = texture2D(uDisplacement, uv).r;
  
  // СИЛА ИСКАЖЕНИЯ (умеренная, чтобы текст оставался читаемым)
  float strength = 0.35 * disp;
  
  vec2 distortion = vec2(strength);
  
  // ХРОМАТИЧЕСКАЯ АБЕРРАЦИЯ (расслоение RGB)
  vec2 uvR = uv - distortion * (0.015 + uAberration);
  vec2 uvG = uv - distortion * 0.015;
  vec2 uvB = uv - distortion * (0.015 - uAberration);
  
  float r = texture2D(uTexture, uvR).r;
  float g = texture2D(uTexture, uvG).g;
  float b = texture2D(uTexture, uvB).b;
  
  gl_FragColor = vec4(r, g, b, 1.0);
}
`

// --------------------------------------------------------
// SCENE CONTENT (Фон + Текст внутри WebGL)
// --------------------------------------------------------
const SceneContent = ({ texture }) => {
    const { viewport } = useThree()
    const scale = useAspect(texture.image.width, texture.image.height, 1)

    // Вычисляем размер текста (clamp эквивалент)
    const baseFontSize = viewport.width * 0.12
    const fontSize = Math.max(0.6, Math.min(baseFontSize, 2.0))

    return (
        <group>
            {/* Background Image */}
            <mesh scale={scale} position={[0, 0, -1]}>
                <planeGeometry />
                <meshBasicMaterial map={texture} toneMapped={false} />
            </mesh>

            {/* Text Group */}
            <group position={[-viewport.width / 2 + 0.5, -viewport.height / 2 + 0.6, 0]}>
                <Text
                    position={[0, fontSize * 0.85, 0]}
                    fontSize={fontSize}
                    lineHeight={0.85}
                    letterSpacing={-0.02}
                    font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hjp-Ek-_EeA.woff"
                    anchorX="left"
                    anchorY="bottom"
                    color="#e5e5e5"
                    outlineWidth={0.002}
                    outlineColor="#000000"
                >
                    SYNTHETIC
                </Text>
                <Text
                    position={[0, 0, 0]}
                    fontSize={fontSize}
                    lineHeight={0.85}
                    letterSpacing={-0.02}
                    font="https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hjp-Ek-_EeA.woff"
                    anchorX="left"
                    anchorY="bottom"
                    color="#e5e5e5"
                    outlineWidth={0.002}
                    outlineColor="#000000"
                >
                    ARCHITECT
                </Text>
            </group>
        </group>
    )
}

// --------------------------------------------------------
// MAIN FLOWMAP SCENE
// --------------------------------------------------------
const FlowmapScene = ({ imageUrl }) => {
    const { size, viewport, gl, camera } = useThree()
    const imageTexture = useTexture(imageUrl)

    // SCENE BUFFER (рендерим фон + текст)
    const sceneBuffer = useFBO(size.width, size.height, {
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
        format: THREE.RGBAFormat,
    })

    // SIMULATION BUFFERS (ping-pong для flowmap)
    const simA = useFBO(size.width / 2, size.height / 2, {
        type: THREE.FloatType,
        format: THREE.RGBAFormat,
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
    })
    const simB = useFBO(size.width / 2, size.height / 2, {
        type: THREE.FloatType,
        format: THREE.RGBAFormat,
        minFilter: THREE.LinearFilter,
        magFilter: THREE.LinearFilter,
    })

    const sceneContentRef = useRef(new THREE.Scene())
    const simScene = useMemo(() => new THREE.Scene(), [])
    const simCamera = useMemo(() => new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1), [])

    const simMat = useRef()
    const dispMat = useRef()

    const mouse = useRef(new THREE.Vector2(0.5, 0.5))
    const lastMouse = useRef(new THREE.Vector2(0.5, 0.5))

    const writeRef = useRef(simA)
    const readRef = useRef(simB)

    useEffect(() => {
        const onMove = (e) => {
            mouse.current.x = e.clientX / window.innerWidth
            mouse.current.y = 1.0 - (e.clientY / window.innerHeight)
        }
        window.addEventListener('mousemove', onMove)
        return () => window.removeEventListener('mousemove', onMove)
    }, [])

    useFrame((state) => {
        if (!simMat.current || !dispMat.current) return

        // 1. RENDER SCENE CONTENT TO BUFFER
        gl.setRenderTarget(sceneBuffer)
        gl.clear()
        gl.render(sceneContentRef.current, camera)
        gl.setRenderTarget(null)

        // 2. SIMULATION PASS
        simMat.current.uniforms.uTexture.value = readRef.current.texture
        simMat.current.uniforms.uMouse.value = mouse.current
        simMat.current.uniforms.uAspect.value = size.width / size.height
        simMat.current.uniforms.uTime.value = state.clock.elapsedTime

        const vel = mouse.current.distanceTo(lastMouse.current)
        simMat.current.uniforms.uVelo.value = Math.min(vel * 30.0, 1.0)
        lastMouse.current.copy(mouse.current)

        gl.setRenderTarget(writeRef.current)
        gl.render(simScene, simCamera)
        gl.setRenderTarget(null)

        // 3. DISPLAY PASS
        dispMat.current.uniforms.uTexture.value = sceneBuffer.texture
        dispMat.current.uniforms.uDisplacement.value = writeRef.current.texture

        // Swap buffers
        const temp = writeRef.current
        writeRef.current = readRef.current
        readRef.current = temp
    })

    return (
        <>
            {createPortal(
                <SceneContent texture={imageTexture} />,
                sceneContentRef.current
            )}

            {createPortal(
                <mesh>
                    <planeGeometry args={[2, 2]} />
                    <shaderMaterial
                        ref={simMat}
                        vertexShader={simVertex}
                        fragmentShader={simFragment}
                        uniforms={{
                            uTexture: { value: null },
                            uMouse: { value: new THREE.Vector2(0, 0) },
                            uAspect: { value: 1 },
                            uVelo: { value: 0 },
                            uTime: { value: 0 }
                        }}
                    />
                </mesh>,
                simScene
            )}

            <mesh scale={[viewport.width, viewport.height, 1]}>
                <planeGeometry args={[1, 1]} />
                <shaderMaterial
                    ref={dispMat}
                    vertexShader={dispVertex}
                    fragmentShader={dispFragment}
                    uniforms={{
                        uTexture: { value: null },
                        uDisplacement: { value: null },
                        uAberration: { value: 0.04 }
                    }}
                />
            </mesh>
        </>
    )
}

export default function LiquidDistortion({ imageUrl }) {
    return (
        <div className="absolute inset-0 w-full h-full">
            <Canvas camera={{ position: [0, 0, 5], fov: 50 }}>
                <FlowmapScene imageUrl={imageUrl} />
            </Canvas>
        </div>
    )
}
