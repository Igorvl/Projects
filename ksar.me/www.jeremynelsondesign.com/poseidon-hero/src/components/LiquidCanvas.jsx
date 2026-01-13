import { useRef, useEffect, useCallback, useState } from 'react'
import html2canvas from 'html2canvas'

/**
 * LiquidCanvas - Displacement distortion overlay
 * Captures content and applies displacement on top
 */
export default function LiquidCanvas({ children }) {
    const containerRef = useRef(null)
    const contentRef = useRef(null)
    const canvasRef = useRef(null)
    const glRef = useRef(null)
    const programRef = useRef(null)
    const textureRef = useRef(null)
    const animationRef = useRef(null)
    const trailsRef = useRef([])
    const textureLoadedRef = useRef(false)

    const vertexShader = `
        attribute vec2 a_position;
        varying vec2 v_uv;
        void main() {
            v_uv = a_position * 0.5 + 0.5;
            gl_Position = vec4(a_position, 0.0, 1.0);
        }
    `

    const fragmentShader = `
        precision highp float;
        varying vec2 v_uv;
        uniform sampler2D u_texture;
        uniform vec2 u_resolution;
        uniform float u_time;
        uniform vec3 u_trails[15];
        uniform int u_trailCount;
        uniform float u_textureLoaded;

        float snoise(vec2 v) {
            return fract(sin(dot(v, vec2(12.9898, 78.233))) * 43758.5453);
        }

        void main() {
            if (u_textureLoaded < 0.5) {
                discard;
                return;
            }

            vec2 uv = v_uv;
            float aspect = u_resolution.x / u_resolution.y;
            vec2 displacement = vec2(0.0);
            float totalStrength = 0.0;

            for (int i = 0; i < 15; i++) {
                if (i >= u_trailCount) break;

                vec2 trailPos = u_trails[i].xy;
                float age = u_trails[i].z;
                float strength = 1.0 - age;
                if (strength <= 0.0) continue;

                vec2 diff = uv - trailPos;
                diff.x *= aspect;
                float dist = length(diff);
                float radius = 0.12;

                if (dist < radius) {
                    float falloff = 1.0 - smoothstep(0.0, radius, dist);
                    falloff = pow(falloff, 1.5);

                    float noise = snoise(uv * 10.0 + u_time) * 0.3;

                    vec2 dir = normalize(diff + 0.0001);
                    displacement += dir * falloff * strength * 0.035 * (1.0 + noise);
                    totalStrength += falloff * strength;
                }
            }

            // Only show distortion when there are active trails
            if (totalStrength < 0.001) {
                discard;
                return;
            }

            vec2 distortedUv = uv + displacement;
            distortedUv = clamp(distortedUv, 0.001, 0.999);

            // Chromatic aberration
            float aberration = totalStrength * 0.003;
            float r = texture2D(u_texture, distortedUv + vec2(aberration, 0.0)).r;
            float g = texture2D(u_texture, distortedUv).g;
            float b = texture2D(u_texture, distortedUv - vec2(aberration, 0.0)).b;

            gl_FragColor = vec4(r, g, b, 1.0);
        }
    `

    const initWebGL = useCallback(() => {
        const canvas = canvasRef.current
        if (!canvas) return false

        const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: false })
        if (!gl) return false

        const vs = gl.createShader(gl.VERTEX_SHADER)
        gl.shaderSource(vs, vertexShader)
        gl.compileShader(vs)

        const fs = gl.createShader(gl.FRAGMENT_SHADER)
        gl.shaderSource(fs, fragmentShader)
        gl.compileShader(fs)

        const program = gl.createProgram()
        gl.attachShader(program, vs)
        gl.attachShader(program, fs)
        gl.linkProgram(program)
        gl.useProgram(program)

        const vertices = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1])
        const buffer = gl.createBuffer()
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
        gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW)

        const posLoc = gl.getAttribLocation(program, 'a_position')
        gl.enableVertexAttribArray(posLoc)
        gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0)

        const texture = gl.createTexture()
        gl.bindTexture(gl.TEXTURE_2D, texture)
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)

        glRef.current = gl
        programRef.current = program
        textureRef.current = texture

        return true
    }, [])

    const captureContent = useCallback(async () => {
        const gl = glRef.current
        const content = contentRef.current
        if (!gl || !content) return

        try {
            const capturedCanvas = await html2canvas(content, {
                backgroundColor: null,
                scale: 1,
                logging: false,
                useCORS: true,
            })

            gl.bindTexture(gl.TEXTURE_2D, textureRef.current)
            gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, capturedCanvas)
            textureLoadedRef.current = true
        } catch (err) {
            console.warn('Capture error:', err)
        }
    }, [])

    const render = useCallback(() => {
        const gl = glRef.current
        const program = programRef.current
        const canvas = canvasRef.current

        if (!gl || !program || !canvas) {
            animationRef.current = requestAnimationFrame(render)
            return
        }

        const time = performance.now() * 0.001

        // Age trails
        trailsRef.current = trailsRef.current
            .map(t => ({ ...t, age: t.age + 0.015 }))
            .filter(t => t.age < 1)

        gl.viewport(0, 0, canvas.width, canvas.height)
        gl.clearColor(0, 0, 0, 0)
        gl.clear(gl.COLOR_BUFFER_BIT)

        gl.uniform2f(gl.getUniformLocation(program, 'u_resolution'), canvas.width, canvas.height)
        gl.uniform1f(gl.getUniformLocation(program, 'u_time'), time)
        gl.uniform1i(gl.getUniformLocation(program, 'u_trailCount'), trailsRef.current.length)
        gl.uniform1f(gl.getUniformLocation(program, 'u_textureLoaded'), textureLoadedRef.current ? 1.0 : 0.0)

        for (let i = 0; i < 15; i++) {
            const loc = gl.getUniformLocation(program, `u_trails[${i}]`)
            if (i < trailsRef.current.length) {
                const t = trailsRef.current[i]
                gl.uniform3f(loc, t.x, 1 - t.y, t.age)
            } else {
                gl.uniform3f(loc, 0, 0, 1)
            }
        }

        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
        animationRef.current = requestAnimationFrame(render)
    }, [])

    const handleMouseMove = useCallback((e) => {
        const rect = containerRef.current?.getBoundingClientRect()
        if (!rect || !textureLoadedRef.current) return

        const x = (e.clientX - rect.left) / rect.width
        const y = (e.clientY - rect.top) / rect.height

        const last = trailsRef.current[trailsRef.current.length - 1]
        const dist = last ? Math.hypot(x - last.x, y - last.y) : 1

        if (dist > 0.015 && trailsRef.current.length < 15) {
            trailsRef.current.push({ x, y, age: 0 })
            // Recapture when distorting
            captureContent()
        }
    }, [captureContent])

    useEffect(() => {
        const canvas = canvasRef.current
        const container = containerRef.current
        if (!canvas || !container) return

        const resize = () => {
            canvas.width = container.offsetWidth
            canvas.height = container.offsetHeight
        }
        resize()

        if (!initWebGL()) return

        // Capture after content renders
        const timer = setTimeout(() => {
            captureContent()
        }, 1000)

        window.addEventListener('resize', resize)
        animationRef.current = requestAnimationFrame(render)

        return () => {
            cancelAnimationFrame(animationRef.current)
            clearTimeout(timer)
            window.removeEventListener('resize', resize)
        }
    }, [initWebGL, captureContent, render])

    return (
        <div
            ref={containerRef}
            className="relative w-full h-full"
            onMouseMove={handleMouseMove}
        >
            {/* Original content - always visible underneath */}
            <div ref={contentRef} className="hero-content w-full h-full">
                {children}
            </div>

            {/* WebGL overlay - shows distorted version only where needed */}
            <canvas
                ref={canvasRef}
                className="absolute inset-0 w-full h-full pointer-events-none z-40"
            />
        </div>
    )
}
