"""Attendre les services HTTP de CI sans accepter une page d’erreur comme disponibilité."""

import argparse
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def wait_for_http(urls: list[str], timeout: float = 60):
    """Attendre chaque endpoint jusqu’à une échéance commune, puis échouer explicitement."""
    deadline = time.monotonic() + timeout
    for url in urls:
        while time.monotonic() < deadline:
            try:
                with urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        print(f"Service prêt : {url}")
                        break
            except (HTTPError, URLError, TimeoutError, OSError):
                pass
            time.sleep(0.5)
        else:
            raise SystemExit(f"Service indisponible après {timeout:g}s : {url}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    wait_for_http(args.urls, args.timeout)
