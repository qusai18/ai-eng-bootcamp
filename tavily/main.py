"""Search the web with Tavily.

Usage:
  python main.py
  python main.py Who is Leo Messi?
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from tavily import TavilyClient


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    load_dotenv(Path(__file__).resolve().parent / ".env")
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        sys.exit("Set TAVILY_API_KEY in .env")

    query = " ".join(sys.argv[1:]).strip() or "Who is Leo Messi?"
    client = TavilyClient(api_key=api_key)
    print(client.search(query))


if __name__ == "__main__":
    main()
