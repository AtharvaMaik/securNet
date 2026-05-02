from scripts.incidents.common import get_parser, post_json

if __name__ == "__main__":
    args = get_parser("Toggle vault dependency failure").parse_args()
    post_json(
        args.vault_url,
        "/simulate/dependency",
        {"dependency_failure": 1 if args.mode == "apply" else 0},
    )
    print(f"vault dependency failure set to {1 if args.mode == 'apply' else 0}")
