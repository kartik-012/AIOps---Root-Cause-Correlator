import React from 'react'

export function RootCausePanel({ incidentDetail, impactData }) {
  const rootName = incidentDetail?.root_cause_service_name || incidentDetail?.root_cause_service || 'Payment Service'
  const rootType = incidentDetail?.root_cause_type
    ? incidentDetail.root_cause_type.replace(/_/g, ' ')
    : 'Connection pool exhaustion'
  const confidence = incidentDetail?.confidence_at_detection
    ? Math.round(incidentDetail.confidence_at_detection * 100)
    : 94
  const impactScore = impactData?.impact_score || 87

  return (
    <div className="panel cause">
      <div className="cause-orb" />

      <h2 className="cause-title">AI reasoning</h2>
      <div className="cause-status">ROOT CAUSE IDENTIFIED</div>
      <h3 className="cause-name">
        {rootType.charAt(0).toUpperCase() + rootType.slice(1)}
      </h3>

      <div className="cause-confidence">
        <span>{confidence}% confidence</span>
        <div className="cause-bar">
          <span style={{ width: `${confidence}%` }} />
        </div>
      </div>

      <p className="cause-desc">
        Pool capacity was reduced during deployment #4821, causing queued
        requests to cascade through checkout.
      </p>
    </div>
  )
}
