from scripts.incidents.common import get_parser, post_json

if __name__ == "__main__":
    args = get_parser("Create or clear scan backlog").parse_args()
    if args.mode == "apply":
        post_json(args.scan_url, "/simulate/backlog", {"multiplier": 3, "jobs": 3})
        print("scan backlog incident applied")
    else:
        post_json(args.scan_url, "/simulate/clear-queue", {})
        post_json(args.scan_url, "/simulate/backlog", {"multiplier": 1, "jobs": 0})
        print("scan backlog cleared and multiplier reset to 1")
