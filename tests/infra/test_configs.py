import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_docker_compose_includes_required_services():
    compose = yaml.safe_load((ROOT / "infra" / "docker-compose.yml").read_text())
    services = compose["services"]
    for name in [
        "api-gateway",
        "auth-service",
        "vault-service",
        "scan-service",
        "prometheus",
        "grafana",
        "alertmanager",
        "loki",
        "promtail",
        "node-exporter",
        "cadvisor",
    ]:
        assert name in services


def test_prometheus_config_scrapes_all_service_jobs():
    prometheus = yaml.safe_load((ROOT / "infra" / "prometheus" / "prometheus.yml").read_text())
    jobs = {job["job_name"] for job in prometheus["scrape_configs"]}
    assert {"api-gateway", "auth-service", "vault-service", "scan-service"} <= jobs


def test_alert_rules_cover_security_and_infrastructure_cases():
    rules = yaml.safe_load((ROOT / "infra" / "prometheus" / "alert_rules.yml").read_text())
    alerts = {
        rule["alert"]
        for group in rules["groups"]
        for rule in group["rules"]
    }
    assert {
        "SecurityServiceDown",
        "HighP95Latency",
        "ContainerMemoryPressure",
        "FailedLoginSpike",
        "SuspiciousTrafficSpike",
    } <= alerts


def test_grafana_dashboards_exist_and_parse():
    dashboard_dir = ROOT / "infra" / "grafana" / "dashboards"
    for name in [
        "service-health.json",
        "infrastructure.json",
        "security-events.json",
        "incident-triage.json",
    ]:
        parsed = json.loads((dashboard_dir / name).read_text())
        assert "title" in parsed
        assert parsed["panels"]
