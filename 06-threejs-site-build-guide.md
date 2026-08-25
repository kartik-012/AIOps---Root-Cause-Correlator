# 📘 threejs-site-build-guide.md

**Implementation guide for the cinematic 3D experience specified in `design.md`.**

Direct note: `design.md` is the visual spec. This file is the engineering plan to actually build it. The interactive site itself is a working HTML/JS/Three.js deliverable — it should exist as real code in your repo (`frontend/showcase/` or as a standalone artifact), not just markdown. Say the word and I'll build the actual working file next; this document is the blueprint so that build isn't started blind.

---

## 1. Tech Stack for the Showcase Site

| Concern | Tool | Why |
|---|---|---|
| 3D rendering | **Three.js** (r160+) | Industry standard, well documented, matches the CDN-importable libraries you already have access to |
| Scroll-linked animation | **GSAP + ScrollTrigger** | Best-in-class for scroll-scrubbed camera/object animation, spring easing built in |
| Particle systems | **Three.js `Points` + `BufferGeometry`** | GPU-instanced, handles thousands of particles without frame drops |
| Glassmorphic UI panels | Plain CSS (`backdrop-filter: blur()`) over WebGL canvas | No need for a heavy UI framework for a single showcase page |
| State (minimal) | Vanilla JS modules | This is a linear scroll experience, not an app — don't add React/Redux overhead here |

---

## 2. File Structure for the Showcase

```
frontend/showcase/
├── index.html
├── styles.css
├── js/
│   ├── scene-hero.js          # Section 2: floating nodes
│   ├── scene-telemetry.js     # Section 3: chaotic → ordered particles
│   ├── scene-correlation.js   # Section 4: 3D dependency graph
│   ├── scene-reasoning.js     # Section 5: AI convergence + reveal
│   ├── scene-timeline.js      # Section 6: horizontal incident timeline
│   ├── panels-design.js       # Section 7: floating glass documentation panels
│   ├── panels-memory.js       # Section 8: memory node visualization
│   ├── explainability.js      # Section 9: evidence reveal panel
│   └── main.js                # scroll orchestration, section transitions
└── assets/
    └── (no external image/video assets needed — everything is procedural WebGL)
```

**Why fully procedural (no image/video assets):** every visual is generated from code (geometry, particles, materials) rather than pre-rendered video — this keeps load times fast and lets every animation stay perfectly synced to scroll position, which a baked video cannot do.

---

## 3. Core Implementation Pattern

### 3.1 Scene Setup (shared across sections)
```javascript
import * as THREE from 'three';

function createScene(container) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // cap for performance
  container.appendChild(renderer.domElement);

  const ambient = new THREE.AmbientLight(0x4A5568, 0.6);
  const point = new THREE.PointLight(0x4EA1FF, 1.2, 50);
  point.position.set(5, 5, 5);
  scene.add(ambient, point);

  return { scene, camera, renderer };
}
```

### 3.2 Hero Floating Nodes (Section 2)
```javascript
const nodeLabels = ['Logs', 'Metrics', 'Traces', 'Alerts', 'Deployments', 'Services'];

function createNode(label, position) {
  const geometry = new THREE.SphereGeometry(0.4, 32, 32);
  const material = new THREE.MeshStandardMaterial({
    color: 0x4EA1FF, metalness: 0.6, roughness: 0.3, emissive: 0x1A3A5C, emissiveIntensity: 0.4
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.copy(position);
  mesh.userData = { label, floatOffset: Math.random() * Math.PI * 2 };
  return mesh;
}

function animateFloat(node, elapsedTime) {
  node.position.y += Math.sin(elapsedTime + node.userData.floatOffset) * 0.001;
}
```

### 3.3 Data Stream Particles (connecting nodes to center)
```javascript
function createDataStream(fromPos, toPos, particleCount = 50) {
  const positions = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount; i++) {
    const t = i / particleCount;
    positions[i * 3] = fromPos.x + (toPos.x - fromPos.x) * t;
    positions[i * 3 + 1] = fromPos.y + (toPos.y - fromPos.y) * t;
    positions[i * 3 + 2] = fromPos.z + (toPos.z - fromPos.z) * t;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({ color: 0x4EA1FF, size: 0.03, transparent: true, opacity: 0.7 });
  return new THREE.Points(geometry, material);
}
```

### 3.4 Scroll-Linked Camera (GSAP ScrollTrigger)
```javascript
gsap.registerPlugin(ScrollTrigger);

gsap.to(camera.position, {
  z: 5,
  scrollTrigger: {
    trigger: '#hero-section',
    start: 'top top',
    end: 'bottom top',
    scrub: 1.2, // inertia — never instant
  }
});
```

### 3.5 Root-Cause Reveal (signature gold moment — Section 5)
```javascript
function revealRootCause(coreNode) {
  gsap.to(coreNode.material.color, { r: 0.949, g: 0.722, b: 0.294, duration: 1.5, ease: 'power2.out' }); // #F2B84B
  gsap.to(coreNode.material, { emissiveIntensity: 1.2, duration: 1.5 });
  gsap.to(coreNode.scale, { x: 1.3, y: 1.3, z: 1.3, duration: 0.8, ease: 'back.out(1.7)' });
}
```
This is the ONLY place gold appears in the entire codebase — enforce that as a rule while building, matching `design.md`'s signature-element principle.

---

## 4. Performance Safeguards (build these in from the start, not after)

```javascript
// Respect reduced motion
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
if (prefersReducedMotion) {
  // Render static final-state frames instead of animating; skip GSAP scroll triggers entirely
}

// Adaptive particle density
const particleCount = window.innerWidth < 768 ? 20 : 50;

// Lazy-load each scene only when its section approaches viewport
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) initScene(entry.target.dataset.scene);
  });
}, { rootMargin: '200px' });
```

---

## 5. Build Order (do not build all 9 sections at once)

1. Hero floating nodes + basic camera (Section 2) — get one scene working end-to-end first
2. Scroll orchestration skeleton (`main.js`) — prove scroll-to-camera linkage works before adding more scenes
3. Telemetry chaos-to-order particles (Section 3)
4. Correlation dependency graph (Section 4) — this is the most complex, budget the most time
5. AI reasoning convergence + gold reveal (Section 5) — the signature moment
6. Incident timeline (Section 6)
7. Glass documentation panels (Section 7)
8. Memory visualization (Section 8)
9. Explainability panel (Section 9)

Ship sections 1–5 as a complete, polished experience before attempting 6–9 — a finished 5-section experience beats a half-built 9-section one, same principle as the engineering side of this project.

---

## 6. Next Step

Confirm and I'll build the actual working `index.html` + Three.js scene (sections 1–2, the hero) as a real rendered artifact you can see and iterate on — that's the fastest way to validate the direction before investing in all 9 sections.
