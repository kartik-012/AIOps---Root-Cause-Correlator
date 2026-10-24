"""Unit tests for Standard OpenTelemetry OTLP/HTTP `/v1/traces` Receiver and Linux eBPF Kernel Probe Engine."""

from app.engines.ebpf_otel_engine import EbpfKernelProbeEngine, OtlpTraceReceiver


def test_otlp_v1_traces_receiver_normalizes_nanos_and_isolates_bottleneck():
    """Verify OtlpTraceReceiver ingests standard OTLP `resourceSpans` JSON and isolates the payment-service SQL bottleneck."""
    receiver = OtlpTraceReceiver()
    payload = receiver.build_sample_otlp_payload(root_cause_service="payment-service")

    res = receiver.ingest_otlp_json(payload)
    assert res["otlp_ingestion_status"] == "ACCEPTED"
    assert res["ingested_spans_count"] == 3

    ta = res["trace_attribution"]
    assert ta["bottleneck_service"] == "payment-service"
    assert "payment_ledger" in ta["bottleneck_operation"]
    assert ta["bottleneck_exclusive_ms"] == 865.0
    assert ta["bottleneck_contribution_pct"] > 90.0

    ebpf = res["ebpf_kernel_correlation"]
    assert ebpf["service_id"] == "payment-service"
    assert ebpf["socket_listen_drops"] > 0
    assert any("futex" in h["hook_name"] for h in ebpf["hooks"])


def test_ebpf_kernel_probe_profiles_distinguish_network_cpu_and_db_faults():
    """Verify EbpfKernelProbeEngine differentiates L4 TCP retransmits, CFS CPU throttling, and DB futex waits."""
    engine = EbpfKernelProbeEngine()

    net_report = engine.inspect_service_kernel_probes("order-service", "network_packet_loss")
    assert net_report.tcp_retransmits_per_sec > 100.0
    assert "tcp:tcp_retransmit_skb" in net_report.kernel_verdict

    cpu_report = engine.inspect_service_kernel_probes("auth-service", "cpu_throttle")
    assert cpu_report.cgroup_throttled_pct > 90.0
    assert cpu_report.runq_latency_p99_us > 10000.0

    db_report = engine.inspect_service_kernel_probes("payment-service", "db_pool_exhaustion")
    assert db_report.socket_listen_drops > 100
    assert "futex" in db_report.kernel_verdict


def test_ebpf_kernel_report_has_critical_hooks():
    """Verify that reports with elevated kprobes correctly report critical hooks present."""
    engine = EbpfKernelProbeEngine()
    db_report = engine.inspect_service_kernel_probes("payment-service", "db_pool_exhaustion")
    assert db_report.has_critical_hooks() is True

