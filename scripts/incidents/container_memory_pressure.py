from scripts.incidents.common import get_parser, post_json

if __name__ == "__main__":
    args = get_parser("Toggle memory pressure on scan-service").parse_args()
    enabled = 1 if args.mode == "apply" else 0
    post_json(args.scan_url, "/simulate/memory-pressure", {"enabled": enabled})
    print(f"scan-service memory pressure set to {enabled}")
