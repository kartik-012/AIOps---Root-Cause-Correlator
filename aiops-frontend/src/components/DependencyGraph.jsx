import React, { useRef, useState, useEffect } from 'react'

/* ─────────────────────────────────────────────
   Unified 2D Dependency Correlation Topology
   Lines are mathematically anchored to the
   exact center coordinates of each node.
   Includes animated energy photon flows.
   ───────────────────────────────────────────── */

const NODES_CONFIG = [
  { id: 'api-gateway', abbr: 'API', name: 'API Gateway', cx: 120, cy: 150, r: 24, isRoot: false },
  { id: 'order-service', abbr: 'ORD', name: 'Order Service', cx: 280, cy: 200, r: 28, isRoot: false },
  { id: 'postgres-primary', abbr: 'DB', name: 'Postgres Primary', cx: 460, cy: 110, r: 42, isRoot: true },
  { id: 'payment-service', abbr: 'PAY', name: 'Payment Service', cx: 620, cy: 205, r: 26, isRoot: false },
  { id: 'inventory', abbr: 'INV', name: 'Inventory', cx: 610, cy: 55, r: 22, isRoot: false },
  { id: 'deploy-4821', abbr: 'DEP', name: 'Deploy #4821', cx: 340, cy: 45, r: 22, isRoot: false },
]

const EDGES_CONFIG = [
  { from: 'api-gateway', to: 'order-service', hot: false },
  { from: 'order-service', to: 'postgres-primary', hot: true },
  { from: 'postgres-primary', to: 'payment-service', hot: true },
  { from: 'postgres-primary', to: 'inventory', hot: false },
  { from: 'deploy-4821', to: 'postgres-primary', hot: true },
]

export function DependencyGraph({ graphData, activeIncident, selectedService, onSelectService }) {
  const rootSvc = activeIncident?.root_cause_service_name || activeIncident?.root_cause_service || 'Postgres Primary'
  const isPostgresOrPayment =
    rootSvc.toLowerCase().includes('payment') ||
    rootSvc.toLowerCase().includes('postgres') ||
    rootSvc.toLowerCase().includes('db')

  // Find node map for center coordinates
  const nodeMap = {}
  NODES_CONFIG.forEach((n) => {
    nodeMap[n.id] = n
  })

  return (
    <div className="panel graph-container-panel">
      <div className="graph-header">
        <div className="graph-title-group">
          <span className="eyebrow">TOPOLOGY CORRELATION</span>
          <h2>Live Microservice Dependency Graph</h2>
        </div>
        <div className="legend">
          <span><em />Healthy Flow</span>
          <span><em className="amber" />Causal Propagation</span>
        </div>
      </div>

      <div className="graph-body-area">
        {/* Subtle radar dotted grid background */}
        <div className="network-grid-bg" />

        {/* SVG with exact mathematical line endpoints */}
        <svg className="graph-svg-layer" viewBox="0 0 760 260" preserveAspectRatio="xMidYMid meet">
          <defs>
            {/* Radial glow filter for root cause */}
            <filter id="goldenGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <filter id="cyanGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Linear gradients for hot edges */}
            <linearGradient id="hotGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#fbbf24" stopOpacity="1" />
            </linearGradient>

            <linearGradient id="nominalGradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#0284c7" stopOpacity="0.7" />
            </linearGradient>
          </defs>

          {/* SVG Connection Lines directly connecting (cx, cy) to (cx, cy) */}
          {EDGES_CONFIG.map((edge, idx) => {
            const p1 = nodeMap[edge.from]
            const p2 = nodeMap[edge.to]
            if (!p1 || !p2) return null

            return (
              <g key={idx} className="edge-group">
                {/* Background thicker blur glow for hot edges */}
                {edge.hot && (
                  <line
                    x1={p1.cx}
                    y1={p1.cy}
                    x2={p2.cx}
                    y2={p2.cy}
                    stroke="#f59e0b"
                    strokeWidth="6"
                    strokeOpacity="0.25"
                    strokeLinecap="round"
                  />
                )}

                {/* Main line */}
                <line
                  className={`edge ${edge.hot ? 'hot' : ''}`}
                  x1={p1.cx}
                  y1={p1.cy}
                  x2={p2.cx}
                  y2={p2.cy}
                  stroke={edge.hot ? 'url(#hotGradient)' : 'url(#nominalGradient)'}
                  strokeWidth={edge.hot ? '2.5' : '1.5'}
                  strokeLinecap="round"
                />

                {/* Animated traveling data photon */}
                <circle r={edge.hot ? '3.5' : '2.5'} fill={edge.hot ? '#fde047' : '#7dd3fc'}>
                  <animateMotion
                    path={`M ${p1.cx} ${p1.cy} L ${p2.cx} ${p2.cy}`}
                    dur={edge.hot ? '1.8s' : '3s'}
                    repeatCount="indefinite"
                  />
                </circle>
              </g>
            )
          })}

          {/* SVG Nodes directly centered at exact (cx, cy) */}
          {NODES_CONFIG.map((node) => {
            const isRoot = node.isRoot && isPostgresOrPayment
            const isSelected = selectedService === node.name
            const displayName = node.isRoot ? rootSvc : node.name

            return (
              <g
                key={node.id}
                className={`svg-node-group ${isRoot ? 'root-node-group' : ''} ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectService && onSelectService(displayName)}
                style={{ cursor: 'pointer' }}
              >
                {/* Root cause outer radar pulsing rings */}
                {isRoot && (
                  <>
                    <circle cx={node.cx} cy={node.cy} r={node.r + 14} className="radar-ring r1" />
                    <circle cx={node.cx} cy={node.cy} r={node.r + 26} className="radar-ring r2" />
                  </>
                )}

                {/* Node outer glow disc */}
                <circle
                  cx={node.cx}
                  cy={node.cy}
                  r={node.r + 2}
                  fill={isRoot ? 'rgba(245, 158, 11, 0.3)' : 'rgba(56, 189, 248, 0.15)'}
                  filter={isRoot ? 'url(#goldenGlow)' : 'url(#cyanGlow)'}
                />

                {/* Main Node Circle */}
                <circle
                  cx={node.cx}
                  cy={node.cy}
                  r={node.r}
                  fill={isRoot ? 'url(#rootNodeGrad)' : 'url(#regularNodeGrad)'}
                  stroke={isRoot ? '#fbbf24' : isSelected ? '#38bdf8' : '#0284c7'}
                  strokeWidth={isRoot ? '2.5' : isSelected ? '2' : '1.2'}
                />

                {/* Node abbreviation text */}
                <text
                  x={node.cx}
                  y={node.cy + (isRoot ? 4 : 3)}
                  textAnchor="middle"
                  fill={isRoot ? '#ffffff' : '#e0f2fe'}
                  fontFamily="'IBM Plex Mono', monospace"
                  fontWeight={isRoot ? '700' : '600'}
                  fontSize={isRoot ? '14' : '10'}
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {node.abbr}
                </text>

                {/* Subtitle label underneath node */}
                <text
                  x={node.cx}
                  y={node.cy + node.r + 15}
                  textAnchor="middle"
                  fill={isRoot ? '#fbbf24' : '#94a3b8'}
                  fontFamily="'Space Grotesk', sans-serif"
                  fontWeight={isRoot ? '600' : '400'}
                  fontSize={isRoot ? '11' : '9.5'}
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {displayName}
                </text>
              </g>
            )
          })}

          {/* Linear / Radial gradients for node fills */}
          <defs>
            <radialGradient id="rootNodeGrad" cx="35%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#fde047" />
              <stop offset="50%" stopColor="#d97706" />
              <stop offset="100%" stopColor="#78350f" />
            </radialGradient>

            <radialGradient id="regularNodeGrad" cx="35%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#38bdf8" />
              <stop offset="60%" stopColor="#0369a1" />
              <stop offset="100%" stopColor="#082f49" />
            </radialGradient>
          </defs>
        </svg>
      </div>
    </div>
  )
}
