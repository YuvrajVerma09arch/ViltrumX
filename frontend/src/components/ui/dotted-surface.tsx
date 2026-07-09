import { useEffect, useRef, type ComponentProps } from 'react'
import * as THREE from 'three'
import { cn } from '@/lib/utils'

type DottedSurfaceProps = Omit<ComponentProps<'div'>, 'ref'>

/**
 * Animated wave-field of dots (Three.js points cloud), used as a decorative
 * backdrop on the landing page. Dark-theme only, like the rest of ViltrumX.
 * Renders a single static frame when the user prefers reduced motion.
 */
export function DottedSurface({ className, ...props }: DottedSurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const SEPARATION = 150
    const AMOUNTX = 40
    const AMOUNTY = 60
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const scene = new THREE.Scene()
    scene.fog = new THREE.Fog(0x0d1117, 2000, 10000)

    const camera = new THREE.PerspectiveCamera(
      60,
      container.clientWidth / container.clientHeight,
      1,
      10000,
    )
    camera.position.set(0, 355, 1220)

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(container.clientWidth, container.clientHeight)
    renderer.setClearColor(0x000000, 0)
    container.appendChild(renderer.domElement)

    const positions: number[] = []
    const colors: number[] = []
    const geometry = new THREE.BufferGeometry()

    // ink-3 (#6e7b8a) dots, fading into the fog
    const dot = new THREE.Color(0x6e7b8a)
    for (let ix = 0; ix < AMOUNTX; ix++) {
      for (let iy = 0; iy < AMOUNTY; iy++) {
        positions.push(
          ix * SEPARATION - (AMOUNTX * SEPARATION) / 2,
          0,
          iy * SEPARATION - (AMOUNTY * SEPARATION) / 2,
        )
        colors.push(dot.r, dot.g, dot.b)
      }
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))

    const material = new THREE.PointsMaterial({
      size: 7,
      vertexColors: true,
      transparent: true,
      opacity: 0.55,
      sizeAttenuation: true,
    })

    const points = new THREE.Points(geometry, material)
    scene.add(points)

    let count = 0
    let animationId = 0

    const renderFrame = () => {
      const positionAttribute = geometry.attributes.position
      const pos = positionAttribute.array as Float32Array

      let i = 0
      for (let ix = 0; ix < AMOUNTX; ix++) {
        for (let iy = 0; iy < AMOUNTY; iy++) {
          pos[i * 3 + 1] =
            Math.sin((ix + count) * 0.3) * 50 +
            Math.sin((iy + count) * 0.5) * 50
          i++
        }
      }
      positionAttribute.needsUpdate = true
      renderer.render(scene, camera)
      count += 0.1
    }

    const animate = () => {
      animationId = requestAnimationFrame(animate)
      renderFrame()
    }

    if (reducedMotion) {
      renderFrame() // one static frame, no loop
    } else {
      animate()
    }

    const handleResize = () => {
      camera.aspect = container.clientWidth / container.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(container.clientWidth, container.clientHeight)
      if (reducedMotion) renderFrame()
    }
    const resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      cancelAnimationFrame(animationId)
      geometry.dispose()
      material.dispose()
      renderer.dispose()
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement)
      }
    }
  }, [])

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      className={cn('pointer-events-none fixed inset-0 -z-10', className)}
      {...props}
    />
  )
}
