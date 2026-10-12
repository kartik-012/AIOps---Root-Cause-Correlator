"""Unit tests verifying Gap #7: Multi-Stage Non-Root Docker Hardening & Compose Immutability."""

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _non_comment_lines(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )


def test_backend_dockerfile_is_multistage_nonroot_and_strips_build_essential():
    """Verify backend/Dockerfile uses multi-stage builder/runtime, drops root, and excludes gcc from runtime."""
    dockerfile = (_repo_root() / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile

    # Split builder and runtime stages
    builder_part, runtime_part = dockerfile.split("AS runtime", 1)
    builder_cmds = _non_comment_lines(builder_part)
    runtime_cmds = _non_comment_lines(runtime_part)

    assert "build-essential" in builder_cmds
    assert "build-essential" not in runtime_cmds

    # Verify non-root user and HEALTHCHECK in runtime stage
    assert "useradd" in runtime_cmds
    assert "USER aiops" in runtime_cmds
    assert "HEALTHCHECK" in runtime_cmds


def test_grpc_dockerfile_is_multistage_and_nonroot():
    """Verify backend/app/grpc_services/Dockerfile.grpc uses multi-stage build and runs as non-root."""
    grpc_dockerfile = (_repo_root() / "backend" / "app" / "grpc_services" / "Dockerfile.grpc").read_text(encoding="utf-8")

    assert "AS builder" in grpc_dockerfile
    assert "AS runtime" in grpc_dockerfile
    assert "USER aiops" in grpc_dockerfile
    assert "HEALTHCHECK" in grpc_dockerfile


def test_docker_compose_does_not_bind_mount_source_or_use_reload():
    """Verify docker-compose.yml preserves container immutability (no ./backend:/app bind mount or --reload)."""
    compose_text = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")

    assert "./backend:/app" not in compose_text
    assert "--reload" not in compose_text
