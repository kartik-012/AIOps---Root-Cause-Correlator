# 📘 design.md

**Cinematic product experience design — AIOps Root Cause Correlator**
**Design philosophy: Apple-level minimalism + enterprise infrastructure intelligence**

---

## 0. Design Tokens

| Token | Value | Use |
|---|---|---|
| Background (base) | `#0B0D12` — deep graphite black | Primary canvas |
| Panel surface | `rgba(255,255,255,0.04)` + backdrop-blur(20px) | Glassmorphic cards |
| Panel border | `rgba(255,255,255,0.08)` hairline | Card edges |
| Accent — data/blue | `#4EA1FF` | Telemetry streams, default node glow |
| Accent — signature gold | `#F2B84B` | Root-cause reveal only — used nowhere else |
| Text primary | `#E8EAED` | Headlines, body |
| Text muted | `#8B93A1` | Captions, labels |
| Display typeface | Space Grotesk | Headlines — geometric, technical |
| Body typeface | Inter | Descriptions, UI copy |
| Data typeface | IBM Plex Mono | Metrics, confidence scores, timestamps |

**Signature element:** one moment, and only one — chaotic telemetry particles collapsing into a single glowing gold node labeled "Root Cause Identified." Every other visual stays quiet blue/graphite so this moment has weight instead of competing with ten other effects.

---

## 1. Overall Visual Language

![AIOps Dashboard Design Reference](assets/dashboard-preview.png)

- Deep black / graphite background throughout — no pure black, `#0B0D12` keeps depth
- Frosted glass surfaces for every panel — translucent, blurred, thin hairline borders
- Soft ambient + volumetric lighting on 3D objects — no hard neon glow
- Subtle metallic material on node spheres (low roughness, soft reflections)
- Depth of field on the hero 3D scene — background nodes blur slightly, foreground stays sharp
- Large cinematic whitespace between sections — nothing feels cramped
- Smooth gradients used only inside glass panels, never as a full-page background wash
- Extremely clean typography — Space Grotesk for headlines, Inter for body, Plex Mono for data
- Explicitly avoided: neon cyberpunk colors, cartoon 3D shapes, excessive gradient noise

**Design rule:** everything has depth and spatial hierarchy, but restraint governs it — Apple-level minimalism, not maximalist sci-fi.

---

## 2. Hero Section — 3D System

**Center:** `AIOps Root Cause Correlator` in large Space Grotesk, letter-spacing slightly widened, sitting at the convergence point of the 3D scene.

**Floating 3D nodes surrounding it, each a distinct labeled sphere:**
- Logs
- Metrics
- Traces
- Alerts
- Deployments
- Services

**Behavior:**
- Nodes float slowly in 3D space with gentle idle motion (subtle sine-wave drift, not distracting)
- Thin animated data-stream lines connect nodes to the center, with particles traveling along them
- On scroll: camera dollies forward slowly, nodes reposition into their next-section formation, data streams activate, particles accelerate, and the central correlator visually "begins processing"

**Technical purpose:** this isn't decoration — the node layout previews the actual data sources the system ingests in Phase 1 of the architecture.

---

## 3. Observability Data Animation

- Thousands of small telemetry particles enter from the edges of the scene, representing Logs, Metrics, Traces, and Alerts as four distinct particle streams (each a subtly different shade of blue, not four unrelated colors)
- Initial state: visually chaotic — particles moving in disordered paths, representing raw unstructured telemetry
- System animates through four visible stages, in order: **filters → normalizes → groups → correlates**
- As each stage completes, visual complexity visibly reduces — chaotic particle motion resolves into orderly, grouped streams

**Technical purpose:** this animation is the visual proof of Phase 2 (Event Processing & Normalization) — noise reduction is shown, not just claimed.

---

## 4. Correlation Engine — 3D Graph

The visual centerpiece of the whole experience.

**Structure:** an interactive 3D service dependency graph, each microservice a glowing node:
```
API Gateway
   ↓
Order Service
   ↓
Payment Service
   ↓
Database
```

**Behavior:**
- Requests animate traveling through the graph edges continuously in the idle state
- When an incident triggers: one node begins showing abnormal activity (color shifts from calm blue toward amber-red)
- Dependent nodes react in sequence, showing the failure propagating outward through real edges, not a generic pulse
- Affected nodes become visually connected with a highlighted path
- The system highlights the probable origin node distinctly from the merely-affected ones

**Camera:** slight orbit/depth movement on scroll so the graph reads as physically three-dimensional, not a flat diagram with a 3D filter.

**Technical purpose:** this is the literal visualization of the Correlation Engine (Phase 3) — dependency mapping, event clustering, and failure propagation, made visible.

---

## 5. AI Root-Cause Reasoning

**Convergence visualization:** six evidence streams visually converge into a central AI reasoning core:
- Logs
- Metrics
- Traces
- Deployment Events
- Service Dependencies
- Historical Incidents

**Sequence:**
1. Evidence streams converge and the AI core visibly "processes" (subtle pulse/breathing animation — not a flashy spinner)
2. Reveal: **ROOT CAUSE IDENTIFIED**
3. Below it: `Database Connection Pool Exhaustion`
4. Below that: `Confidence: 94%` *(illustrative demo data, clearly labeled as such — never presented as a real production metric)*
5. Supporting evidence appears one item at a time, not all at once — each evidence line fades in with a short delay so the user reads it as a build-up of proof, not a wall of text

**Technical purpose:** this is Phase 4 (AI Root-Cause Analysis) — and it is the one section where the signature gold accent color appears, marking this as the single most important reveal in the whole experience.

---

## 6. Cinematic Incident Timeline

**Layout:** horizontally scrolling 3D timeline.

```
Deployment → Latency Increase → Error Spike → Service Failure → Correlation → Root Cause
```

**Behavior, scroll-linked:**
- Camera follows the active event as the user scrolls horizontally
- Each event rises subtly from the timeline surface as it becomes active
- Evidence cards appear beside the active event
- Related telemetry (the specific metric spike or trace anomaly tied to that event) illuminates
- Root-cause relationships become visually traceable — a thin light line connects the final root-cause event back to the deployment that triggered it

**Technical purpose:** demonstrates the Incident Analyzer's timeline reconstruction — turning six isolated events into one causal story.

---

## 7. Design.md Experience (Interactive Documentation)

Instead of flat cards, the documentation itself becomes floating translucent glass panels covering:
- Incident UI
- Visual Language
- Typography & Data
- AI Explainability

**Panel behavior:**
- Float with subtle idle motion
- React to cursor position — slight rotation toward the cursor, simulating physical presence
- Cast soft, realistic depth-aware shadows
- Expand smoothly (spring easing, not linear) when selected, revealing full section content

---

## 8. Memory.md Experience (Incident Memory)

**Visualization:** historical incidents represented as floating memory nodes, each showing:
```
Past Incident → Root Cause → Resolution → Learned Pattern → Future Detection
```

**Behavior on new incident:**
1. System visibly "searches" historical memory — a soft sweeping highlight passes across the memory node field
2. Relevant historical incidents visually move toward the current incident node
3. Reveal: **"Similar incident detected"**

**Technical purpose:** demonstrates the false-positive suppression / historical-memory engine from the architecture — showing, not just claiming, that past incidents inform current analysis.

---

## 9. AI Explainability Panel

Explicitly designed so the AI is never a black box.

**Sequence:**
1. Show: `Root Cause Hypothesis`
2. Animate supporting evidence appearing one at a time, each with a checkmark:
   - ✓ Metric anomaly
   - ✓ Trace latency
   - ✓ Recent deployment
   - ✓ Dependency failure
   - ✓ Historical similarity

**Interaction:** the user can hover/select any evidence line to see the underlying data point it's drawn from — reinforcing that every claim traces back to something real, per the AI-boundaries principle in `rules.md`.

---

## 10. Scroll Animations

Every major section transition is scroll-driven and cinematic:

| Technique | Where used |
|---|---|
| Fade + depth movement | Section-to-section transitions |
| 3D parallax | Hero → Observability Data |
| Camera dolly | Hero, Correlation Graph |
| Object rotation | Correlation Graph nodes |
| Scale transitions | AI reasoning core reveal |
| Particle movement | Observability Data, Memory search |
| Graph transformation | Correlation Engine incident state |
| Glass panel expansion | design.md documentation panels |
| Morphing between system states | Chaotic telemetry → correlated graph |

**Motion principle:** spring physics + smooth easing + inertia throughout. No abrupt cuts or hard linear animations anywhere in the experience.

---

## 11. 3D Micro-Interactions

**Buttons:**
- Slight elevation on hover
- Soft shadow increase
- Tiny scale increase (105% max, never cartoonish)
- Smooth press-down animation on click

**Cards:**
- 3D tilt following cursor position
- Dynamic lighting response
- Glass reflection shift
- Depth-aware shadow that grows/shrinks with elevation

**Graph nodes:**
- Hovered nodes move slightly toward the viewer
- Connected edges illuminate
- Related services highlight simultaneously

**AI elements:**
- Subtle breathing animation on the reasoning core (idle state)
- Particle movement during active processing
- A gentle "processing pulse" that never becomes a generic loading spinner

---

## 12. Apple-Level Transitions

The entire experience is designed as one continuous visual story rather than separate pages:

```
Chaotic telemetry cloud
      ↓ compresses into
Correlation graph
      ↓ transforms into
Root-cause path
      ↓ transforms into
Incident report
```

No hard page breaks — every section resolves visually into the next one's starting state.

---

## 13. Performance Requirements

Visual richness must never come at the cost of usability:

- GPU-accelerated animations only
- Efficient WebGL/Three.js rendering — instanced geometry for repeated nodes/particles
- Lazy loading of 3D assets, loaded progressively as sections approach viewport
- Reduced particle density on mobile devices
- Full respect for `prefers-reduced-motion` — static, still-elegant fallback states for every animated section
- 60 FPS target on desktop; adaptive rendering quality steps down gracefully on lower-end hardware
- Every animation must have a **technical purpose** — no decoration for its own sake

---

## 14. Final Impression Goal

The experience should communicate, within seconds:

> "This isn't just an AI project. This person understands production systems."

**Visual story arc:**
```
Observe → Correlate → Reason → Explain → Remember → Respond → Improve
```

**Explicitly avoided throughout:**
- Generic admin dashboard look
- Plain rectangular cards with no depth
- Neon cyberpunk color palettes
- Random unmotivated 3D decoration
- Any animation that doesn't map to real system behavior

**Guiding principle:** Apple's restraint and polish applied to a genuinely technical subject — every visual element earns its place by representing something the system actually does.
