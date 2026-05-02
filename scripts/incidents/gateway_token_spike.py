import httpx

from scripts.incidents.common import get_parser

if __name__ == "__main__":
    args = get_parser("Generate invalid token traffic through the gateway").parse_args()
    if args.mode == "reset":
        print("gateway token spike is traffic-driven; stop the generator to reset")
    else:
        for _ in range(200):
            httpx.get(
                f"{args.gateway_url}/scan/queue",
                headers={
                    "authorization": "Bearer invalid-token",
                    "x-forwarded-for": "198.51.100.40",
                },
                timeout=5.0,
            )
        print("gateway token validation spike generated")
