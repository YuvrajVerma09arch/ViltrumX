import { useEffect, useRef, type ComponentProps } from 'react'
import * as THREE from 'three'
import { cn } from '@/lib/utils'

type WebGLShaderProps = Omit<ComponentProps<'div'>, 'ref'>

const VERTEX_SHADER = `
attribute vec3 position;
void main() {
  gl_Position = vec4(position, 1.0);
}
`

const FRAGMENT_SHADER = `
precision highp float;
uniform vec2 resolution;
uniform float time;
uniform float xScale;
uniform float yScale;
uniform float distortion;

void main() {
  vec2 p = (gl_FragCoord.xy * 2.0 - resolution) / min(resolution.x, resolution.y);

  float d = length(p) * distortion;

  float rx = p.x * (1.0 + d);
  float gx = p.x;
  float bx = p.x * (1.0 - d);

  float r = 0.05 / abs(p.y + sin((rx + time) * xScale) * yScale);
  float g = 0.05 / abs(p.y + sin((gx + time) * xScale) * yScale);
  float b = 0.05 / abs(p.y + sin((bx + time) * xScale) * yScale);

  // ViltrumX tint: green-dominant beams with chromatic fringes, over the app bg
  vec3 beams = vec3(r * 0.30, g * 0.95, b * 0.45);
  vec3 base = vec3(0.051, 0.067, 0.090); /* #0d1117 */
  gl_FragColor = vec4(base + beams, 1.0);
}
`

/**
 * Full-bleed neon-wave fragment shader (single quad, cheap to render).
 * Fills its container; renders one static frame under prefers-reduced-motion.
 */
export function WebGLShader({ className, ...props }: WebGLShaderProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const canvas = document.createElement('canvas')
    canvas.className = 'block h-full w-full'
    container.appendChild(canvas)

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)

    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, -1)

    const uniforms = {
      resolution: { value: new THREE.Vector2(1, 1) },
      time: { value: reducedMotion ? 6.0 : 0.0 },
      xScale: { value: 1.0 },
      yScale: { value: 0.5 },
      distortion: { value: 0.05 },
    } satisfies Record<string, THREE.IUniform>

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute(
      'position',
      new THREE.BufferAttribute(
        new Float32Array([
          -1, -1, 0, 1, -1, 0, -1, 1, 0,
          1, -1, 0, -1, 1, 0, 1, 1, 0,
        ]),
        3,
      ),
    )

    const material = new THREE.RawShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms,
      side: THREE.DoubleSide,
    })

    const mesh = new THREE.Mesh(geometry, material)
    scene.add(mesh)

    let animationId = 0
    const renderFrame = () => renderer.render(scene, camera)
    const animate = () => {
      animationId = requestAnimationFrame(animate)
      uniforms.time.value += 0.01
      renderFrame()
    }

    const handleResize = () => {
      const w = container.clientWidth
      const h = container.clientHeight
      renderer.setSize(w, h, false)
      // gl_FragCoord is in device pixels — resolution must match the buffer
      uniforms.resolution.value.set(w * window.devicePixelRatio, h * window.devicePixelRatio)
      if (reducedMotion) renderFrame()
    }
    handleResize()

    if (reducedMotion) {
      renderFrame()
    } else {
      animate()
    }

    const resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      cancelAnimationFrame(animationId)
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      if (canvas.parentElement === container) container.removeChild(canvas)
    }
  }, [])

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className={cn('pointer-events-none absolute inset-0', className)}
      {...props}
    />
  )
}
