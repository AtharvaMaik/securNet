from scripts.incidents.common import get_parser, post_json

if __name__ == "__main__":
    args = get_parser("Toggle auth-service latency spike").parse_args()
    latency = 900 if args.mode == "apply" else 15
    post_json(args.auth_url, "/simulate", {"latency_ms": latency})
    print(f"auth-service latency set to {latency}ms")
