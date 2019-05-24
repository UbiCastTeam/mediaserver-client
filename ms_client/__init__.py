import sys

from .client import MediaServerClient


__all__ = ["MediaServerClient"]

with open("version.txt") as v:
    __version__ = v.read()

if __name__ == "__main__":
    local_conf = sys.argv[1] if len(sys.argv) > 1 else None
    msc = MediaServerClient(local_conf)
    # ping
    print(msc.api("/"))
