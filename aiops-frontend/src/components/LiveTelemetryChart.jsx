import React, { useEffect, useState } from 'react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { Panel } from './Panel'

export function LiveTelemetryChart({ selectedService }) {
  const [data, setData] = useState([])

  // Generate continuous rolling telemetry points
  useEffect(() => {
    const generateInitialData = () => {
      const points = []
      const now = Date.now()
      for (let i = 15; i >= 0; i--) {
        const timeStr = new Date(now - i * 3000).toTimeString().split(' ')[0]
        const isSpike = selectedService?.toLowerCase().includes('payment') && i < 4
        const val = isSpike ? 85.0 + Math.random() * 12.0 : 25.0 + Math.sin(i) * 4.0 + Math.random() * 2.0
        const ewma = 26.0 + Math.sin(i) * 2.0
        points.push({
          time: timeStr,
          metric: Math.round(val),
          ewma: Math.round(ewma),
          upperThreshold: 45,
        })
      }
      return points
    }

    setData(generateInitialData())

    const interval = setInterval(() => {
      setData((prev) => {
        const nowStr = new Date().toTimeString().split(' ')[0]
        const isSpike = selectedService?.toLowerCase().includes('payment')
        const val = isSpike ? 88.0 + Math.random() * 10.0 : 25.0 + Math.random() * 5.0
        const ewma = 27.0 + Math.random() * 2.0

        const newPoint = {
          time: nowStr,
          metric: Math.round(val),
          ewma: Math.round(ewma),
          upperThreshold: 45,
        }
        return [...prev.slice(1), newPoint]
      })
    }, 3000)

    return () => clearInterval(interval)
  }, [selectedService])

  return (
    <Panel className="telemetry-chart-panel">
      <div className="section-head">
        <div>
          <span className="eyebrow">STREAMING TELEMETRY & ADAPTIVE BASELINE</span>
          <h2>{selectedService || 'Payment Service'} · Real-time EWMA Anomaly Analysis</h2>
        </div>
        <div className="chart-legend-row">
          <span className="legend-item"><i className="leg-actual" /> Ingested Metric</span>
          <span className="legend-item"><i className="leg-ewma" /> EWMA Baseline</span>
          <span className="legend-item"><i className="leg-thresh" /> Threshold (2.5σ)</span>
        </div>
      </div>

      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="metricGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="ewmaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
            <XAxis
              dataKey="time"
              stroke="#718096"
              fontSize={10}
              fontFamily="IBM Plex Mono"
              minTickGap={45}
              interval="preserveStartEnd"
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
            />
            <YAxis
              stroke="#718096"
              fontSize={10}
              fontFamily="IBM Plex Mono"
              tickLine={{ stroke: 'rgba(255, 255, 255, 0.1)' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0d1219',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                fontFamily: 'IBM Plex Mono',
                fontSize: '11px',
              }}
            />
            <Area
              type="monotone"
              dataKey="metric"
              stroke="#f59e0b"
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#metricGrad)"
              name="Active Value"
            />
            <Area
              type="monotone"
              dataKey="ewma"
              stroke="#38bdf8"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              fillOpacity={1}
              fill="url(#ewmaGrad)"
              name="EWMA Baseline"
            />
            <Line
              type="monotone"
              dataKey="upperThreshold"
              stroke="#ef4444"
              strokeWidth={1}
              strokeDasharray="2 2"
              dot={false}
              name="Adaptive Threshold"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  )
}
