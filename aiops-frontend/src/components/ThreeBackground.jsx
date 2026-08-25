import React, { useEffect, useRef } from 'react'
import * as THREE from 'three'

/* ─────────────────────────────────────────────
   3D Ambient Particle Constellation
   Soft circular glowing dust with mouse parallax
   Zero blocky square artifacts.
   ───────────────────────────────────────────── */

function createCircleTexture() {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32)
  g.addColorStop(0, 'rgba(255, 255, 255, 1)')
  g.addColorStop(0.3, 'rgba(78, 161, 255, 0.75)')
  g.addColorStop(0.7, 'rgba(30, 80, 160, 0.25)')
  g.addColorStop(1, 'rgba(0, 0, 0, 0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 64, 64)
  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  return texture
}

export function ThreeBackground({ hasActiveAnomaly }) {
  const mountRef = useRef(null)

  useEffect(() => {
    const container = mountRef.current
    if (!container) return

    // Scene setup
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      0.1,
      1000
    )
    camera.position.z = 80

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(renderer.domElement)

    // Particle Cloud Geometry
    const particleCount = 180
    const geometry = new THREE.BufferGeometry()
    const positions = new Float32Array(particleCount * 3)
    const colors = new Float32Array(particleCount * 3)
    const velocities = []

    const colorNormal = new THREE.Color(0x38bdf8) // Electric cyan
    const colorAmber = new THREE.Color(0xf59e0b) // Amber gold

    for (let i = 0; i < particleCount; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 160
      positions[i * 3 + 1] = (Math.random() - 0.5) * 110
      positions[i * 3 + 2] = (Math.random() - 0.5) * 70

      const isWarn = Math.random() < 0.2
      const c = isWarn ? colorAmber : colorNormal
      colors[i * 3] = c.r
      colors[i * 3 + 1] = c.g
      colors[i * 3 + 2] = c.b

      velocities.push({
        x: (Math.random() - 0.5) * 0.03,
        y: (Math.random() - 0.5) * 0.03,
        z: (Math.random() - 0.5) * 0.03,
      })
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

    // Material with soft circular texture
    const circleTex = createCircleTexture()
    const material = new THREE.PointsMaterial({
      size: 2.2,
      map: circleTex,
      vertexColors: true,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })

    const particleSystem = new THREE.Points(geometry, material)
    scene.add(particleSystem)

    // Mouse Parallax
    let mouseX = 0
    let mouseY = 0
    let targetX = 0
    let targetY = 0

    const onMouseMove = (e) => {
      mouseX = (e.clientX - window.innerWidth / 2) * 0.0004
      mouseY = (e.clientY - window.innerHeight / 2) * 0.0004
    }
    window.addEventListener('mousemove', onMouseMove)

    // Window Resize Handler
    const onResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', onResize)

    // Animation Loop
    let animationId
    const animate = () => {
      animationId = requestAnimationFrame(animate)

      targetX += (mouseX - targetX) * 0.05
      targetY += (mouseY - targetY) * 0.05

      camera.rotation.y = targetX
      camera.rotation.x = targetY

      // Float particles
      const pos = particleSystem.geometry.attributes.position.array
      for (let i = 0; i < particleCount; i++) {
        pos[i * 3] += velocities[i].x
        pos[i * 3 + 1] += velocities[i].y
        pos[i * 3 + 2] += velocities[i].z

        if (pos[i * 3] > 80 || pos[i * 3] < -80) velocities[i].x *= -1
        if (pos[i * 3 + 1] > 55 || pos[i * 3 + 1] < -55) velocities[i].y *= -1
        if (pos[i * 3 + 2] > 35 || pos[i * 3 + 2] < -35) velocities[i].z *= -1
      }
      particleSystem.geometry.attributes.position.needsUpdate = true
      particleSystem.rotation.y += 0.0005

      renderer.render(scene, camera)
    }

    animate()

    return () => {
      cancelAnimationFrame(animationId)
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('resize', onResize)
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
      geometry.dispose()
      material.dispose()
      circleTex.dispose()
      renderer.dispose()
    }
  }, [])

  return (
    <div
      ref={mountRef}
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
        opacity: 0.75,
      }}
    />
  )
}
