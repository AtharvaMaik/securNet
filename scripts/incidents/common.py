from __future__ import annotations

import argparse
import os

import httpx


def get_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--mode", choices=["apply", "reset"], required=True)
    parser.add_argument("--gateway-url", default=os.getenv("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--auth-url", default=os.getenv("AUTH_URL", "http://localhost:8001"))
    parser.add_argument("--vault-url", default=os.getenv("VAULT_URL", "http://localhost:8002"))
    parser.add_argument("--scan-url", default=os.getenv("SCAN_URL", "http://localhost:8003"))
    return parser


def post_json(base_url: str, path: str, payload: dict) -> None:
    response = httpx.post(f"{base_url}{path}", json=payload, timeout=10.0)
    response.raise_for_status()

