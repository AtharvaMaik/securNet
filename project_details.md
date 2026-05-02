# Project Details

This document is the full explanation of the project: what it is, why it exists, how it works, where the data comes from, what each technology is doing, and why the system is structured the way it is.

## 1. What this project is

`Security Observability Platform` is a simulated internal security infrastructure stack plus a complete observability layer around it.

The application side of the project looks like a small security control plane:

- an API gateway receives requests
- an auth service issues and validates tokens
- a vault service simulates secrets access
- a scan service simulates background security scan jobs

The observability side of the project answers operational questions such as:

- Are the services up?
- Are requests getting slower?
- Are errors increasing?
- Are authentication failures spiking?
- Is a dependency unhealthy?
- Is the scan queue backing up?
- Is the host or process under resource pressure?
- If an alert fires, what should an engineer look at first?

This means the repo is not just "an app" and not just "a monitoring demo." It is both:

- a simulated system worth monitoring
- the tooling and procedures needed to monitor it

## 2. What the project does

At a high level, the project does seven things:

1. Runs a small multi-service platform.
2. Exposes metrics from every service.
3. Collects host and runtime telemetry.
4. Aggregates logs for triage.
5. Visualizes all of that in Grafana.
6. Fires alerts for important failure conditions.
7. Lets you intentionally trigger incidents to prove the observability works.

## 3. Why build this project

A normal CRUD app can show API development skills, but it usually does not demonstrate operational depth.

This project was built to show stronger engineering capabilities:

- instrumentation and telemetry design
- service reliability thinking
- security event observability
- incident diagnosis
- alert tuning
- runbook documentation
- deployment awareness

In other words, it is designed to look and behave more like internal platform engineering or InfoSec SRE work than a simple web app.

## 4. What problem observability is solving here

Any distributed system becomes harder to operate as soon as there are multiple services and dependencies.

When something goes wrong, engineers need to answer questions like:

- Which service is failing?
- Is the service down, slow, or just overloaded?
- Is the problem caused by the service itself or by one of its dependencies?
- Is the issue affecting normal traffic or security-specific workflows?
- Is this a real incident or a false positive?

Observability is the set of tools and signals that helps answer those questions from the outside.

This project uses three main kinds of observability data:

- metrics
- logs
- alerts

## 5. What each service is doing

### `api-gateway`

This is the public-facing entrypoint.

Its responsibilities are:

- receive external requests
- validate tokens through `auth-service`
- route traffic to `vault-service` and `scan-service`
- record edge-focused telemetry such as suspicious bursts, rate limiting, and upstream health
- host the hybrid operator console at `/`

Why it exists:

- real platforms usually have an edge layer
- it makes dependency health more realistic
- it gives the observability stack one clear "front door" to monitor

### `auth-service`

This simulates authentication behavior.

Its responsibilities are:

- accept login requests
- issue synthetic tokens
- validate tokens
- record failed logins, invalid headers, and token validation failures

Why it exists:

- auth systems are central to security platforms
- auth failures are meaningful security and reliability signals
- token validation gives the gateway a realistic upstream dependency

### `vault-service`

This simulates secret retrieval and secret backend health.

Its responsibilities are:

- respond to secret access requests
- expose dependency failure simulation
- record secret access errors

Why it exists:

- secrets and dependency health are common operational pain points
- it creates a meaningful "security infrastructure" dependency rather than just another generic API

### `scan-service`

This simulates queued background work.

Its responsibilities are:

- accept scan job submissions
- maintain an internal queue
- process jobs in the background
- expose queue depth, backlog, and worker health signals

Why it exists:

- queue-based work is common in internal security systems
- it creates useful metrics like backlog depth and processing duration
- it gives the project a strong incident story beyond HTTP request metrics

## 6. What the observability stack is doing

### Prometheus

Prometheus is a metrics collection and query system.

In this project it:

- scrapes `/metrics` endpoints from every FastAPI service
- scrapes infrastructure exporters
- stores time series metrics
- evaluates recording rules
- evaluates alert rules

Why use it:

- it is the standard open-source choice for service and infrastructure metrics
- its pull model is simple for containerized services
- PromQL is expressive enough for error rates, percentiles, queue depth, and anomaly-oriented views

### Grafana

Grafana is the visualization layer.

In this project it:

- reads metrics from Prometheus
- reads logs from Loki
- renders dashboards for service health, infrastructure, security events, and incident triage

Why use it:

- it is flexible and widely used
- it lets us combine multiple data sources in one place
- it turns raw telemetry into operator-friendly views

### Alertmanager

Alertmanager handles alert routing and grouping.

In this project it:

- receives alerts from Prometheus
- groups them
- routes them to a local mock webhook target

Why use it:

- it makes the observability stack feel operational rather than dashboard-only
- it mirrors how alerts move through real systems

### Loki and Promtail

Loki is the log store. Promtail is the log shipper.

In this project:

- services write structured logs
- Promtail tails those logs
- Loki stores them
- Grafana shows them in incident dashboards

Why use them:

- logs provide context that metrics alone cannot
- Loki is a natural companion to Grafana
- structured logs are especially useful during incident investigation

### Node Exporter

Node Exporter exposes host-level metrics from the machine.

In this project it gives us:

- CPU
- memory
- disk
- network

Why use it:

- host state is a critical part of infrastructure observability
- application metrics alone cannot explain machine-level pressure

### cAdvisor

cAdvisor exposes container runtime metrics.

In this project it exists because:

- container-aware telemetry is a common part of Docker-based monitoring
- it rounds out the platform's infra story

Important note:

on Docker Desktop and Windows, cAdvisor does not always expose the same container metadata richness you would get on Linux. That is why some dashboard panels were moved to process-level metrics for better reliability in this environment.

## 7. What Docker is

Docker is a container platform.

A container is a packaged runtime environment that includes:

- the application code
- its dependencies
- the runtime needed to execute it

Why we use Docker here:

- every service can run the same way on different machines
- the observability stack can be started with one command
- the local environment stays reproducible
- deployment to EC2 is simpler because the same containers can run there

## 8. What Docker Compose is

Docker Compose is a way to define and run multiple containers together.

Instead of manually starting each service, the repo describes the full stack in one file:

- application services
- Prometheus
- Grafana
- Alertmanager
- Loki
- Promtail
- Node Exporter
- cAdvisor

Why we use it:

- this project is inherently multi-service
- Compose makes local parity easy
- it is simple enough for local use and a single-host EC2 deployment

## 9. What EC2 is

EC2 stands for Amazon Elastic Compute Cloud.

An EC2 instance is basically a virtual machine running in AWS.

Why EC2 matters here:

- it is a realistic cloud deployment target
- it lets the project be "cloud-deployed" without requiring Kubernetes
- it is easier to explain and cheaper to run than a fully managed orchestration platform for a personal project

Why we did not make EC2 the only mode:

- always-on cloud infrastructure costs money
- local parity is better for portability and demos
- recruiters care more about the architecture and observability workflow than about paying to keep a demo online all month

## 10. Where the data is coming from

There are several sources of data in the system.

### Application metrics

Each FastAPI service exposes `/metrics` using `prometheus_client`.

Those metrics include:

- request counts
- latency histograms
- error counters
- queue depth
- dependency health
- security event counters

This data is generated by the services themselves.

### Infrastructure metrics

These come from exporters:

- Node Exporter for host metrics
- cAdvisor for container/runtime metrics
- process metrics exposed directly by the Python services and other components

### Logs

Logs are written by the services in structured JSON format.

Promtail reads those logs and sends them to Loki.

### Alerts

Alerts are not a separate original data source. They are derived from Prometheus queries and rules.

For example:

- if latency crosses a threshold, Prometheus evaluates that condition and emits an alert
- Alertmanager then routes it

## 11. How the data moves through the system

The data flow looks like this:

1. A request hits `api-gateway`.
2. The gateway may call `auth-service`, `vault-service`, or `scan-service`.
3. Each service records metrics and logs about what happened.
4. Prometheus scrapes those metrics.
5. Prometheus stores them and evaluates rules.
6. Grafana queries Prometheus for dashboard panels.
7. Promtail ships logs into Loki.
8. Grafana queries Loki for incident log context.
9. If an alert condition is true, Prometheus sends an alert to Alertmanager.

## 12. Why metrics, logs, and alerts all matter

### Metrics

Metrics answer:

- how much
- how often
- how fast
- how many failures

They are good for dashboards and alerting.

### Logs

Logs answer:

- what exactly happened
- what payload or path was involved
- what the service said internally at the time

They are good for investigation.

### Alerts

Alerts answer:

- should a human pay attention now

They are good for response, not deep diagnosis by themselves.

## 13. Why the dashboards are separated

Grafana dashboards are split by operational question.

### Service Health

Shows:

- are services up
- how much traffic they are handling
- whether errors are growing
- whether latency is increasing
- whether dependencies are healthy

### Security Events

Shows:

- failed logins
- token validation failures
- burst traffic
- rate limiting
- secrets access problems
- queue backlog

### Infrastructure

Shows:

- host CPU
- host memory
- service CPU
- service memory
- disk usage
- network traffic

### Incident Triage

Shows:

- active/firing condition signals
- dependency state history
- recent logs

This split helps each dashboard stay purpose-driven rather than becoming one giant wall of graphs.

## 14. Why we built incident simulations

A dashboard is much more convincing when it reacts to something meaningful.

That is why the repo includes controlled incidents such as:

- auth latency spike
- scan backlog growth
- vault dependency failure
- token validation spike
- memory pressure

Why that matters:

- it proves the metrics are not decorative
- it proves the alert rules are wired correctly
- it gives you a reliable demo path
- it creates better interview talking points

## 15. Why the alerts exist

Alerts are meant to represent the kinds of conditions an operator would care about in a real environment.

Examples:

- service down
- dependency unhealthy
- high 5xx rate
- high latency
- queue backlog too high
- suspicious auth spikes
- memory pressure

Why we use thresholds:

- the goal is not just to collect data
- the goal is to turn important conditions into actionable signals

## 16. Why we wrote runbooks and docs

Good monitoring is not just charts and thresholds.

A good operational system also answers:

- what does this alert mean
- what is likely causing it
- what should I check next
- what do I do to mitigate it

That is why the repo includes:

- architecture docs
- dashboard docs
- alert docs
- runbook docs
- AWS comparison notes

## 17. Why we are doing what we are doing right now

Right now, the work is about making the project production-presentable.

That means:

- the system should actually run
- the dashboards should actually load
- the panels should not be obviously broken or empty for the wrong reasons
- the README should explain the project clearly to another engineer or recruiter
- the deep-dive doc should explain the concepts to someone who is less familiar with cloud and observability tooling

This is important because a repo is not judged only by code quality.

It is also judged by:

- clarity
- reliability
- completeness
- how easy it is for someone else to understand what they are looking at

## 18. Why specific technology choices were made

### Why Python

- fast to build service simulations
- strong observability libraries
- easy to read
- good fit for a monorepo demo

### Why FastAPI

- quick API development
- built-in OpenAPI docs
- clean async support
- easy middleware and metrics integration

### Why Prometheus instead of only CloudWatch

- stronger service-level metric querying
- richer open-source observability workflow
- better local development story
- widely recognized for SRE-style monitoring

### Why Grafana

- flexible dashboards
- integrates cleanly with both Prometheus and Loki
- strong operator experience

### Why Loki instead of a heavier log stack

- simpler to run for this project
- natural Grafana integration
- enough for structured-log triage use cases

### Why EC2 instead of ECS or Kubernetes

- easier to understand for a personal project
- cheaper and simpler to explain
- still cloud-relevant
- matches the single-host Compose deployment model well

## 19. What is real and what is simulated

Real in this project:

- the services
- the metrics collection
- the dashboards
- the alerts
- the logs
- the incident simulations
- the Docker and EC2 deployment story

Simulated in this project:

- the underlying business/security logic
- token issuance and validation behavior
- secret backend behavior
- queue and worker load patterns
- injected failures

That is intentional. The goal is not to build a real security product. The goal is to build a realistic observability environment around a security-themed platform.

## 20. How to think about the project as a portfolio artifact

This repo demonstrates:

- application instrumentation
- distributed system monitoring
- security-centric signal design
- dashboard design
- alert routing
- incident simulation
- deployment planning
- operator documentation

That combination is what makes it stronger than a normal demo project.

## 21. Files worth reading next

If you want the shortest path through the repo:

1. `README.md`
2. `docs/architecture.md`
3. `infra/docker-compose.yml`
4. `infra/prometheus/prometheus.yml`
5. `infra/prometheus/recording_rules.yml`
6. `infra/prometheus/alert_rules.yml`
7. `services/api_gateway/app.py`
8. `shared/metrics.py`
9. `docs/runbook.md`

## 22. Final summary

This project is a simulated security platform wrapped in a real observability system.

The services generate activity.
The observability stack turns that activity into metrics, logs, dashboards, and alerts.
The incident scripts prove the monitoring works.
The docs explain how an operator should respond.

That is the core idea: not just building software, but building the operational visibility needed to trust and support it.
