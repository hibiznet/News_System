from http.server import HTTPServer, SimpleHTTPRequestHandler
import json, os

class Handler(SimpleHTTPRequestHandler):
    def do_PUT(self):
        length = int(self.headers['Content-Length'])
        data = self.rfile.read(length)

        with open(self.path.lstrip("/"), "wb") as f:
            f.write(data)

        self.send_response(200)
        self.end_headers()

os.chdir(os.path.dirname(__file__))
HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
