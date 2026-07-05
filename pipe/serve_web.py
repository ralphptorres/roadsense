import functools
import http.server
import pathlib
import sys

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB))
    with http.server.ThreadingHTTPServer(("localhost", port), handler) as httpd:
        print(f"serving {WEB} at http://localhost:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
