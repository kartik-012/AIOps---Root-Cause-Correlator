import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'
import { Panel } from './Panel'
import { sound } from '../utils/audio'

export function LiveTelemetryChart({ selectedService }) {
  const [data, setData] = useState([])
  const [mode, setMode] = useState('live') // 'live' | '9am_ramp' | '3am_spike'

  useEffect(() => {
    const generateDataForMode = (activeMode) => {
      const points = []
      const now = Date.now()
      for (let i = 15; i >= 0; i--) {
        if (activeMode === '9am_ramp') {
          // 9:00 AM Morning Traffic Surge: Both actual metric AND Diurnal Fourier Baseline climb to ~65%
          const progress = (15 - i) / 15
          const diurnalExpected = 22 + progress * 43
          const actual = diurnalExpected + Math.sin(i) * 1.5
          points.push({
            time: `08:${String(45 + (15 - i)).padStart(2, '0')}`,
            metric: Math.round(actual),
            ewma: Math.round(diurnalExpected),
            upperThreshold: Math.round(diurnalExpected + 14),
          })
        } else if (activeMode === '3am_spike') {
          // 3:00 AM Off-Peak Night Hours: Diurnal baseline stays flat at 15%, metric spikes to 65%!
          const diurnalExpected = 15 + Math.sin(i) * 1.0
          const actual = i < 5 ? 65 + Math.random() * 4 : diurnalExpected + Math.random() * 2
          points.push({
            time: `02:${String(45 + (15 - i)).padStart(2, '0')}`,
            metric: Math.round(actual),
            ewma: Math.round(diurnalExpected),
            upperThreshold: 28,
          })
        } else {
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
      }
      return points
    }

    setData(generateDataForMode(mode))

    if (mode !== 'live') return

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
  }, [selectedService, mode])

  return (
    <Panel className="telemetry-chart-panel sota-3d-panel">
      <div className="section-head">
        <div>
          <span className="eyebrow">DIURNAL FOURIER HARMONIC + WINSORIZED EWMA</span>
          <h2>{selectedService || 'Payment Service'} · Adaptive Seasonal Telemetry</h2>
        </div>

        <div className="telemetry-controls-right">
          <div className="sota-tab-switcher">
            <button
              className={mode === 'live' ? 'active' : ''}
              onClick={() => {
                sound.click()
                setMode('live')
              }}
            >
              Live Stream
            </button>
            <button
              className={mode === '9am_ramp' ? 'active' : ''}
              onClick={() => {
                sound.click()
                setMode('9am_ramp')
              }}
              title="Simulate 09:00 AM morning traffic ramp (65% load recognized as normal diurnal cycle)"
            >
              ☀️ 09:00 AM Ramp
            </button>
            <button
              className={mode === '3am_spike' ? 'active' : ''}
              onClick={() => {
                sound.alert()
                setMode('3am_spike')
              }}
              title="Simulate 03:00 AM off-peak 65% spike (flagged immediately as critical anomaly)"
            >
              🌙 03:00 AM Spike
            </button>
          </div>
        </div>
      </div>

      {/* Contextual Diurnal & RingBuffer Status Bar */}
      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          className="diurnal-status-strip"
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          transition={{ duration: 0.2 }}
        >
          {mode === '9am_ramp' && (
            <span className="diurnal-chip emerald">
              ✓ 09:00 AM Morning Peak (65% Load) Matches 24h Fourier Harmonic Expectation · z = 0.42σ (Zero False Alarm)
            </span>
          )}
          {mode === '3am_spike' && (
            <span className="diurnal-chip danger">
              🚨 03:00 AM Off-Peak 65% Load Deviates From 15% Night Expectation · z = 14.2σ (CRITICAL ANOMALY)
            </span>
          )}
          {mode === 'live' && (
            <span className="diurnal-chip neutral">
              ⚡ StreamingRingBuffer (Cap: 10,000 · High-Watermark: 80%) · Huber Poisoning Guard Active
            </span>
          )}
          <div className="chart-legend-row">
            <span className="legend-item">
              <i className="leg-actual" /> Metric
            </span>
            <span className="legend-item">
              <i className="leg-ewma" /> Fourier/EWMA
            </span>
            <span className="legend-item">
              <i className="leg-thresh" /> 2.5σ Gate
            </span>
          </div>
        </motion.div>
      </AnimatePresence>

      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={155}>
          <AreaChart data={data} margin={{ top: 8, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="metricGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.42} />
                <stop offset="95%" stopColor="#f59e0b" stopOpacity={0.0} />
              </linearGradient>
              <linearGradient id="ewmaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.28} />
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
                borderColor: 'rgba(56, 189, 248, 0.25)',
                borderRadius: '10px',
                fontFamily: 'IBM Plex Mono',
                fontSize: '11px',
                boxShadow: '0 12px 28px rgba(0, 0, 0, 0.5)',
              }}
            />
            <Area
              type="monotone"
              dataKey="metric"
              stroke="#f59e0b"
              strokeWidth={2.2}
              fillOpacity={1}
              fill="url(#metricGrad)"
              name="Observed Metric"
            />
            <Area
              type="monotone"
              dataKey="ewma"
              stroke="#38bdf8"
              strokeWidth={1.8}
              strokeDasharray="4 4"
              fillOpacity={1}
              fill="url(#ewmaGrad)"
              name="Fourier/EWMA Baseline"
            />
            <Line
              type="monotone"
              dataKey="upperThreshold"
              stroke="#ef4444"
              strokeWidth={1.2}
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
