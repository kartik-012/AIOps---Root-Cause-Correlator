import React, { useState } from 'react'
import { sound } from '../utils/audio'

export function RunbookPanel({ incidentDetail, onApprove }) {
  const [approved, setApproved] = useState(false)

  return (
    <div className="panel runbook">
      <h2>Recommended response</h2>
      <p>
        Rollback pool configuration, then drain long-running checkout
        connections.
      </p>
      {approved ? (
        <div className="approved-badge">✓ Runbook Approved & Executing</div>
      ) : (
        <button
          className="approve-btn"
          onClick={() => {
            sound.success()
            setApproved(true)
            onApprove && onApprove()
          }}
        >
          Open verified runbook →
        </button>
      )}
    </div>
  )
}
