import React, { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { sound } from '../utils/audio'

/* ─────────────────────────────────────────────────────────────
   Cinematic 3D Spatial Neural Mesh (Apple / Google Tier)
   - 60 FPS Zero-Lag Direct DOM Matrix Projected Service Tags
   - Names move in 100% fluid lockstep with the rotating 3D spheres
   - Bulletproof Raycasting with Metadata Traversal
   - Real-time Interactive HUD with Live Metrics
   ───────────────────────────────────────────────────────────── */

const SERVICES_FLEET = [
  { id: 'api-gateway', abbr: 'API', name: 'API Gateway', pos: [0, 13, 0], metrics: '1,840 req/s · 18ms latency', statusText: 'Healthy (200 OK)', status: 'nominal' },
  { id: 'auth-service', abbr: 'AUTH', name: 'Auth Service', pos: [-15, 6, -3], metrics: '420 req/s · 11ms latency', statusText: 'Healthy (JWT Verified)', status: 'nominal' },
  { id: 'product-catalog', abbr: 'CAT', name: 'Product Catalog', pos: [-7, 2, 7], metrics: '890 req/s · 22ms latency', statusText: 'Healthy (Cache Warm)', status: 'nominal' },
  { id: 'order-service', abbr: 'ORD', name: 'Order Service', pos: [11, 4, -2], metrics: '650 req/s · 210ms latency (Cascade)', statusText: 'Cascade Degraded (P1)', status: 'warning' },
  { id: 'inventory-service', abbr: 'INV', name: 'Inventory Service', pos: [-11, -8, 3], metrics: '310 req/s · 14ms latency', statusText: 'Healthy (Nominal)', status: 'nominal' },
  { id: 'payment-service', abbr: 'PAY', name: 'Payment Service', pos: [5, -9, 2], metrics: 'HikariPool Saturation: 99.8% · 1,450ms Latency', statusText: 'CRITICAL (Root Cause Origin)', status: 'critical' },
  { id: 'notification-service', abbr: 'NOTIF', name: 'Notification Service', pos: [17, -4, 5], metrics: '120 req/s · 4ms latency', statusText: 'Healthy (Nominal)', status: 'nominal' },
  { id: 'shipping-service', abbr: 'SHIP', name: 'Shipping Service', pos: [19, -11, -4], metrics: '95 req/s · 16ms latency', statusText: 'Healthy (Nominal)', status: 'nominal' },
]

const EDGES_FLEET = [
  ['api-gateway', 'auth-service'],
  ['api-gateway', 'product-catalog'],
  ['product-catalog', 'inventory-service'],
  ['api-gateway', 'order-service'],
  ['order-service', 'payment-service'],
  ['order-service', 'inventory-service'],
  ['order-service', 'notification-service'],
  ['order-service', 'shipping-service'],
]

function createGlowSprite(colorHex, size) {
  const canvas = document.createElement('canvas')
  canvas.width = 128
  canvas.height = 128
  const ctx = canvas.getContext('2d')
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64)
  g.addColorStop(0, colorHex)
  g.addColorStop(0.35, colorHex + 'aa')
  g.addColorStop(0.7, colorHex + '44')
  g.addColorStop(1, 'transparent')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, 128, 128)
  const tex = new THREE.CanvasTexture(canvas)
  const mat = new THREE.SpriteMaterial({
    map: tex,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  })
  const sprite = new THREE.Sprite(mat)
  sprite.scale.set(size, size, 1)
  return sprite
}

export function ThreeTopologyView({ graphData, activeIncident, selectedService, onSelectService }) {
  const mountRef = useRef(null)
  const controlsRef = useRef(null)
  const cameraRef = useRef(null)
  const tagElementsRef = useRef({})
  const [activeHUD, setActiveHUD] = useState({
    name: 'Payment Service',
    statusText: 'CRITICAL (Root Cause Origin)',
    metrics: 'HikariPool Saturation 99.8% · 1,450ms Latency',
    status: 'critical',
  })
  const [cameraMode, setCameraMode] = useState('orbit')

  const rootId = activeIncident?.root_cause_service_name || activeIncident?.root_cause_service || 'Payment Service'
  const rootLower = rootId.toLowerCase()

  useEffect(() => {
    const container = mountRef.current
    if (!container) return

    const width = container.clientWidth || 800
    const height = 440

    // ── 1. Scene & Fog ──
    const scene = new THREE.Scene()
    scene.fog = new THREE.FogExp2(0x060c14, 0.009)

    // ── 2. Camera ──
    const camera = new THREE.PerspectiveCamera(50, width / height, 0.1, 600)
    camera.position.set(0, 14, 48)
    cameraRef.current = camera

    // ── 3. WebGL Renderer ──
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' })
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.3
    container.appendChild(renderer.domElement)

    // ── 4. OrbitControls ──
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.06
    controls.minDistance = 15
    controls.maxDistance = 85
    controls.autoRotate = cameraMode === 'orbit'
    controls.autoRotateSpeed = 0.55
    controls.maxPolarAngle = Math.PI * 0.78
    controlsRef.current = controls

    // ── 5. Lighting ──
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5)
    scene.add(ambientLight)

    const mainLight = new THREE.DirectionalLight(0x38bdf8, 1.2)
    mainLight.position.set(20, 30, 20)
    scene.add(mainLight)

    const fillLight = new THREE.DirectionalLight(0x818cf8, 0.6)
    fillLight.position.set(-20, -10, -20)
    scene.add(fillLight)

    const rootPointLight = new THREE.PointLight(0xf59e0b, 3.5, 70)
    rootPointLight.position.set(5, -9, 2)
    scene.add(rootPointLight)

    // ── 6. Tactical Grid Floor (Deep space) ──
    const gridHelper = new THREE.GridHelper(90, 45, 0x1e3a8a, 0x0f172a)
    gridHelper.position.y = -22
    gridHelper.material.transparent = true
    gridHelper.material.opacity = 0.25
    scene.add(gridHelper)

    // ── 7. Particle Starfield Dust ──
    const starGeom = new THREE.BufferGeometry()
    const starCount = 500
    const starPositions = new Float32Array(starCount * 3)
    for (let i = 0; i < starCount; i++) {
      starPositions[i * 3] = (Math.random() - 0.5) * 180
      starPositions[i * 3 + 1] = (Math.random() - 0.5) * 180
      starPositions[i * 3 + 2] = (Math.random() - 0.5) * 180
    }
    starGeom.setAttribute('position', new THREE.BufferAttribute(starPositions, 3))
    const starMat = new THREE.PointsMaterial({
      color: 0x38bdf8,
      size: 0.2,
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
    })
    scene.add(new THREE.Points(starGeom, starMat))

    // ── 8. Service Nodes Setup ──
    const nodeMeshes = []
    const svcMap = {}
    const nodeWorldPositions = {}
    const shockwaves = []
    const edgeParticleSystems = []
    let rootNodePos = new THREE.Vector3(5, -9, 2)

    SERVICES_FLEET.forEach((s) => {
      const isRoot = s.id.includes(rootLower) || s.name.toLowerCase().includes(rootLower)
      const isAffected = !isRoot && (s.id.includes('order') || s.id.includes('api'))
      const posVec = new THREE.Vector3(s.pos[0], s.pos[1], s.pos[2])

      if (isRoot) {
        rootNodePos.copy(posVec)
      }

      // Sphere Geometry
      const coreRadius = isRoot ? 2.8 : 1.8
      const sphereGeo = new THREE.SphereGeometry(coreRadius, 32, 32)
      const mat = new THREE.MeshPhysicalMaterial({
        color: isRoot ? 0xf59e0b : isAffected ? 0xf97316 : 0x0284c7,
        emissive: isRoot ? 0xd97706 : isAffected ? 0xc2410c : 0x0369a1,
        emissiveIntensity: isRoot ? 1.5 : isAffected ? 0.75 : 0.4,
        roughness: 0.1,
        metalness: 0.85,
        clearcoat: 1.0,
        clearcoatRoughness: 0.1,
      })

      const mesh = new THREE.Mesh(sphereGeo, mat)
      mesh.position.copy(posVec)
      mesh.userData = {
        id: s.id,
        name: s.name,
        isRoot,
        isAffected,
        metrics: s.metrics,
        statusText: isRoot ? 'CRITICAL (Root Cause Origin)' : isAffected ? 'Cascade Degraded (P1)' : s.statusText,
        status: isRoot ? 'critical' : isAffected ? 'warning' : 'nominal',
      }
      scene.add(mesh)
      nodeMeshes.push(mesh)
      svcMap[s.id] = posVec
      nodeWorldPositions[s.id] = posVec

      // Outer rotating geometric wireframe cage
      const cageGeo = new THREE.IcosahedronGeometry(coreRadius * 1.32, 1)
      const cageMat = new THREE.MeshBasicMaterial({
        color: isRoot ? 0xfde047 : isAffected ? 0xfdba74 : 0x38bdf8,
        wireframe: true,
        transparent: true,
        opacity: isRoot ? 0.85 : 0.4,
      })
      const cage = new THREE.Mesh(cageGeo, cageMat)
      cage.userData = mesh.userData
      mesh.add(cage)

      // Add radial glow sprite
      const glowSprite = createGlowSprite(isRoot ? '#f59e0b' : isAffected ? '#f97316' : '#38bdf8', isRoot ? 18 : 9)
      glowSprite.position.copy(posVec)
      scene.add(glowSprite)

      // Multi-layer spinning orbital rings for root cause
      if (isRoot) {
        for (let r = 0; r < 3; r++) {
          const ringGeo = new THREE.TorusGeometry(coreRadius * (1.8 + r * 0.45), 0.06, 16, 80)
          const ringMat = new THREE.MeshBasicMaterial({
            color: 0xfde047,
            transparent: true,
            opacity: 0.85 - r * 0.2,
          })
          const ring = new THREE.Mesh(ringGeo, ringMat)
          ring.rotation.x = Math.PI / 4 + r * 0.4
          ring.rotation.y = r * 0.6
          ring.userData = { ringSpeed: (r + 1) * 0.8, ...mesh.userData }
          mesh.add(ring)
        }
      }
    })

    // ── 9. Volumetric Sonar Shockwaves around Root Cause ──
    for (let i = 0; i < 3; i++) {
      const ringGeo = new THREE.RingGeometry(1, 1.4, 64)
      const ringMat = new THREE.MeshBasicMaterial({
        color: 0xf59e0b,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
      })
      const wave = new THREE.Mesh(ringGeo, ringMat)
      wave.position.set(rootNodePos.x, rootNodePos.y - 4, rootNodePos.z)
      wave.rotation.x = Math.PI / 2
      wave.userData = { phase: i * (Math.PI * 2 / 3), speed: 0.025 }
      scene.add(wave)
      shockwaves.push(wave)
    }

    // ── 10. Bezier Curved 3D Laser Tubes & Data Streams ──
    EDGES_FLEET.forEach(([src, tgt]) => {
      const p1 = svcMap[src]
      const p2 = svcMap[tgt]
      if (!p1 || !p2) return

      const isHot = src.includes(rootLower) || tgt.includes(rootLower)

      const mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5)
      mid.y += 2.5
      mid.z += (Math.random() - 0.5) * 2

      const curve = new THREE.QuadraticBezierCurve3(p1, mid, p2)
      const tubeGeo = new THREE.TubeGeometry(curve, 36, isHot ? 0.16 : 0.08, 8, false)
      const tubeMat = new THREE.MeshBasicMaterial({
        color: isHot ? 0xf59e0b : 0x0284c7,
        transparent: true,
        opacity: isHot ? 0.9 : 0.35,
      })
      const tube = new THREE.Mesh(tubeGeo, tubeMat)
      scene.add(tube)

      const particleCount = isHot ? 24 : 10
      const geom = new THREE.BufferGeometry()
      const posArray = new Float32Array(particleCount * 3)
      const offsets = new Float32Array(particleCount)

      for (let i = 0; i < particleCount; i++) {
        offsets[i] = i / particleCount
        const pt = curve.getPoint(offsets[i])
        posArray[i * 3] = pt.x
        posArray[i * 3 + 1] = pt.y
        posArray[i * 3 + 2] = pt.z
      }

      geom.setAttribute('position', new THREE.BufferAttribute(posArray, 3))
      const mat = new THREE.PointsMaterial({
        color: isHot ? 0xfde047 : 0x7dd3fc,
        size: isHot ? 0.48 : 0.26,
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })

      const ps = new THREE.Points(geom, mat)
      ps.userData = { curve, offsets, speed: isHot ? 0.008 : 0.004 }
      scene.add(ps)
      edgeParticleSystems.push(ps)
    })

    // ── 11. Helper to find valid service metadata from any raycast hit ──
    const getServiceMetadata = (hitObject) => {
      let cur = hitObject
      while (cur) {
        if (cur.userData && cur.userData.name) return cur.userData
        cur = cur.parent
      }
      return null
    }

    // ── 12. Interactive Raycasting Click & Hover ──
    const raycaster = new THREE.Raycaster()
    const mouse = new THREE.Vector2()

    const onPointerMove = (e) => {
      const rect = renderer.domElement.getBoundingClientRect()
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1

      raycaster.setFromCamera(mouse, camera)
      const intersects = raycaster.intersectObjects(nodeMeshes, true)
      if (intersects.length > 0) {
        const meta = getServiceMetadata(intersects[0].object)
        if (meta && meta.name) {
          setActiveHUD(meta)
          renderer.domElement.style.cursor = 'pointer'
        }
      } else {
        renderer.domElement.style.cursor = 'grab'
      }
    }

    const onClick = (e) => {
      const rect = renderer.domElement.getBoundingClientRect()
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1

      raycaster.setFromCamera(mouse, camera)
      const intersects = raycaster.intersectObjects(nodeMeshes, true)
      if (intersects.length > 0) {
        sound.click()
        const meta = getServiceMetadata(intersects[0].object)
        if (meta && meta.name) {
          setActiveHUD(meta)
          if (onSelectService) onSelectService(meta.name)
        }
      }
    }

    renderer.domElement.addEventListener('mousemove', onPointerMove)
    renderer.domElement.addEventListener('click', onClick)
    renderer.domElement.addEventListener('mousedown', () => { renderer.domElement.style.cursor = 'grabbing' })
    renderer.domElement.addEventListener('mouseup', () => { renderer.domElement.style.cursor = 'grab' })

    // ── 13. Direct 60 FPS DOM Transform Projection (Zero React State Lag) ──
    const updateDOMTagPositions = () => {
      const w = container.clientWidth || 800
      const h = container.clientHeight || 440
      const tempVec = new THREE.Vector3()

      SERVICES_FLEET.forEach((s) => {
        const el = tagElementsRef.current[s.id]
        if (!el) return

        const worldPos = nodeWorldPositions[s.id]
        if (!worldPos) return

        tempVec.copy(worldPos)
        tempVec.project(camera)

        const isBehind = tempVec.z >= 1
        const screenX = (tempVec.x * 0.5 + 0.5) * w
        const screenY = (-(tempVec.y * 0.5) + 0.5) * h

        const isRoot = s.id.includes(rootLower) || s.name.toLowerCase().includes(rootLower)
        const yOffset = isRoot ? 32 : 24

        // Hide tags that are behind the camera or off screen
        if (isBehind || screenX < -60 || screenX > w + 60 || screenY < -60 || screenY > h + 60) {
          el.style.opacity = '0'
          el.style.pointerEvents = 'none'
        } else {
          el.style.opacity = '1'
          el.style.pointerEvents = 'auto'
          // Smooth 60fps direct hardware GPU translation
          el.style.transform = `translate3d(${screenX}px, ${screenY + yOffset}px, 0)`
        }
      })
    }

    // ── 14. Main Animation Loop ──
    let animId
    const clock = new THREE.Clock()

    const animate = () => {
      animId = requestAnimationFrame(animate)
      const t = clock.getElapsedTime()

      controls.update()

      // Scaling breathing pulse
      nodeMeshes.forEach((mesh, idx) => {
        const isRoot = mesh.userData.isRoot
        const isAffected = mesh.userData.isAffected

        if (isRoot) {
          const s = 1.0 + 0.1 * Math.sin(t * 3.5)
          mesh.scale.set(s, s, s)
          rootPointLight.intensity = 3.0 + 1.2 * Math.sin(t * 4)
        } else if (isAffected) {
          const s = 1.0 + 0.05 * Math.sin(t * 5 + idx)
          mesh.scale.set(s, s, s)
        }

        mesh.children.forEach((child) => {
          if (child.userData?.ringSpeed) {
            child.rotation.z += 0.015 * child.userData.ringSpeed
          } else {
            child.rotation.x += 0.008
            child.rotation.y += 0.01
          }
        })
      })

      // Animate shockwaves
      shockwaves.forEach((sw) => {
        sw.userData.phase += sw.userData.speed
        if (sw.userData.phase > Math.PI * 2) sw.userData.phase = 0
        const scale = 1.0 + sw.userData.phase * 4
        sw.scale.set(scale, scale, 1)
        sw.material.opacity = Math.max(0, 0.75 * (1 - sw.userData.phase / (Math.PI * 2)))
      })

      // Animate photon data streams
      edgeParticleSystems.forEach((ps) => {
        const { curve, offsets, speed } = ps.userData
        const pos = ps.geometry.attributes.position.array

        for (let i = 0; i < offsets.length; i++) {
          offsets[i] = (offsets[i] + speed) % 1
          const pt = curve.getPoint(offsets[i])
          pos[i * 3] = pt.x
          pos[i * 3 + 1] = pt.y
          pos[i * 3 + 2] = pt.z
        }
        ps.geometry.attributes.position.needsUpdate = true
      })

      renderer.render(scene, camera)
      updateDOMTagPositions()
    }

    animate()

    // ── 15. Window resize ──
    const onResize = () => {
      const w = container.clientWidth
      camera.aspect = w / height
      camera.updateProjectionMatrix()
      renderer.setSize(w, height)
    }
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(animId)
      renderer.domElement.removeEventListener('mousemove', onPointerMove)
      renderer.domElement.removeEventListener('click', onClick)
      window.removeEventListener('resize', onResize)
      controls.dispose()
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement)
      }
      renderer.dispose()
    }
  }, [graphData, activeIncident, cameraMode])

  // Camera presets
  const handleCameraPreset = (mode) => {
    sound.click()
    setCameraMode(mode)
    if (!controlsRef.current || !cameraRef.current) return
    const camera = cameraRef.current
    const controls = controlsRef.current

    if (mode === 'orbit') {
      controls.autoRotate = true
      camera.position.set(0, 14, 48)
      controls.target.set(0, 0, 0)
    } else if (mode === 'root') {
      controls.autoRotate = false
      camera.position.set(10, -3, 16)
      controls.target.set(5, -9, 2)
    }
  }

  return (
    <div className="three-topology-container">
      <div ref={mountRef} className="three-canvas" />

      {/* 100% Vector-Sharp 60 FPS Direct Projected HTML Node Badges */}
      <div className="three-html-labels-layer">
        {SERVICES_FLEET.map((s) => {
          const isRoot = s.id.includes(rootLower) || s.name.toLowerCase().includes(rootLower)
          const isAffected = !isRoot && (s.id.includes('order') || s.id.includes('api'))
          const isSelected = (selectedService || '').toLowerCase().includes(s.name.toLowerCase())

          return (
            <div
              key={s.id}
              ref={(el) => {
                if (el) tagElementsRef.current[s.id] = el
              }}
              className={`three-projected-tag ${isRoot ? 'tag-root' : isAffected ? 'tag-affected' : 'tag-nominal'} ${isSelected ? 'tag-selected' : ''}`}
              onClick={() => {
                sound.click()
                setActiveHUD({
                  name: s.name,
                  statusText: isRoot ? 'CRITICAL (Root Cause Origin)' : isAffected ? 'Cascade Degraded (P1)' : s.statusText,
                  metrics: s.metrics,
                  status: isRoot ? 'critical' : isAffected ? 'warning' : 'nominal',
                })
                if (onSelectService) onSelectService(s.name)
              }}
            >
              <span className={`tag-dot ${isRoot ? 'dot-root' : isAffected ? 'dot-affected' : 'dot-nominal'}`} />
              <b className="tag-name">{s.name}</b>
            </div>
          )
        })}
      </div>

      {/* Live Telemetry Node Inspector HUD (Top Left) */}
      <div className="three-node-hud-card">
        <div className="hud-header">
          <span className={`hud-dot ${activeHUD.status || 'nominal'}`} />
          <b className="hud-title">{activeHUD.name}</b>
          <span className={`hud-status-tag ${activeHUD.status || 'nominal'}`}>
            {activeHUD.statusText || 'Healthy'}
          </span>
        </div>
        <p className="hud-metric-line">{activeHUD.metrics || 'Telemetry streams nominal'}</p>
        <div className="hud-action-hint">✨ Click any 3D node to filter dashboard telemetry</div>
      </div>

      {/* Top Camera Controls Toolbar */}
      <div className="three-camera-toolbar">
        <button
          className={`cam-btn ${cameraMode === 'orbit' ? 'active' : ''}`}
          onClick={() => handleCameraPreset('orbit')}
        >
          🔄 360° Auto-Orbit
        </button>
        <button
          className={`cam-btn ${cameraMode === 'root' ? 'active' : ''}`}
          onClick={() => handleCameraPreset('root')}
        >
          🎯 Focus Root Cause
        </button>
      </div>

      {/* Bottom Status Legend */}
      <div className="three-legend">
        <span className="tl-root">● Probable Origin (Pulsing)</span>
        <span className="tl-affected">● Cascade Affected</span>
        <span className="tl-healthy">● Nominal Flow</span>
      </div>
    </div>
  )
}
