# AWS Comparison

## Why EC2 + Compose

EC2 keeps the runtime cost predictable while still giving the project a real cloud deployment story. The same Compose topology used locally can run on a single instance with persistent volumes and systemd-managed startup.

## What CloudWatch would cover

With the CloudWatch agent on the EC2 host, you would typically collect:

- host CPU, memory, and disk metrics
- system logs
- Docker or application log files
- custom metrics if emitted through the CloudWatch agent or API

## Why Prometheus, Grafana, and Loki are still used here

CloudWatch is useful for host-centric monitoring and native AWS operations, but this project leans on Prometheus and Grafana because they provide:

- direct application metric scraping
- richer histogram support for latency and quantiles
- flexible PromQL for security event rates and queue analytics
- first-class dashboard control for interview demos
- easy correlation of logs and metrics with Loki in one UI

## Complementary model

The intended production-style story is:

- CloudWatch for EC2 host visibility, alarms, and baseline AWS-native integration
- Prometheus and Grafana for detailed service and security observability
- Loki for searchable local/service logs that line up with Prometheus alerts

## CloudWatch agent notes

The EC2 deployment assets include a placeholder CloudWatch agent config path. A practical rollout would:

1. install the CloudWatch agent
2. point it at `/var/log/security-platform/*.log`
3. publish host memory and disk metrics
4. optionally mirror container logs into a CloudWatch log group for backup retention
