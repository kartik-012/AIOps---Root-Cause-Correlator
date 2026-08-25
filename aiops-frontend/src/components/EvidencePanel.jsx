import React, { useState } from 'react'

export function EvidencePanel({ explanation, onEvidenceClick }) {
  const defaultEvidence = [
    { text: 'Connection waits +418%', time: '08:30' },
    { text: 'Trace latency propagated', time: '08:34' },
    { text: 'Deployment config change', time: '08:27' },
    { text: 'Historical match found', time: '0.91' },
  ]

  const evidenceItems =
    explanation?.evidence && explanation.evidence.length > 0
      ? explanation.evidence.map((e) =>
          typeof e === 'string' ? { text: e, time: '' } : e
        )
      : defaultEvidence

  return (
    <div className="panel evidence">
      <h2>Evidence chain</h2>
      <div className="evidence-list">
        {evidenceItems.map((item, idx) => (
          <div
            key={idx}
            className="evidence-row"
            onClick={() => onEvidenceClick && onEvidenceClick(item.text || item)}
          >
            <b className="ev-check">✓</b>
            <span>{item.text || item}</span>
            <span className="ev-time">{item.time || ''}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
