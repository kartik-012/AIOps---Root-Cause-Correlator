import React from 'react'

export function IncidentTimeline({ incidentDetail, onSelectEvent }) {
  const events = [
    { time: '08:27:04', label: 'Deployment', isFinal: false },
    { time: '08:30:17', label: 'Pool growth', isFinal: false },
    { time: '08:34:42', label: 'Latency spike', isFinal: false },
    { time: '08:37:15', label: 'Error cascade', isFinal: false },
    { time: '08:41:33', label: 'Root cause', isFinal: true },
  ]

  return (
    <div className="panel timeline-panel">
      <div className="timeline-header">
        <div>
          <span className="eyebrow">CAUSAL NARRATIVE</span>
          <h2>Incident reconstruction</h2>
        </div>
        <span className="expand-link">Expand timeline ↗</span>
      </div>

      <div className="events-track">
        {events.map((evt, idx) => (
          <div
            key={idx}
            className={`event-step ${evt.isFinal ? 'final' : ''}`}
            onClick={() => onSelectEvent && onSelectEvent(evt)}
          >
            <i />
            <b>{evt.time}</b>
            <span>{evt.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
