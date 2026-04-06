from __future__ import annotations

import argparse

from find_your_job.webapp import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Find Your Job web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
