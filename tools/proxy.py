from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.parse
import json
import base64

# ── CONFIG ──────────────────────────────────────────────────────
# Paste your Anthropic API key here
ANTHROPIC_API_KEY = 'YOUR_ANTHROPIC_API_KEY_HERE'
# ────────────────────────────────────────────────────────────────

class ProxyHandler(SimpleHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == '/parse-injuries':
            self._handle_parse_injuries()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path.startswith('/fetch-pdf?'):
            self._handle_fetch_pdf()
        else:
            super().do_GET()

    def _handle_fetch_pdf(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        target_url = params.get('url', [None])[0]

        if not target_url or 'nba.com' not in target_url:
            self.send_response(400)
            self.end_headers()
            return

        try:
            req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()

            self.send_response(200)
            self._cors_headers()
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def _handle_parse_injuries(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
            pdf_url = body.get('url')

            if not pdf_url or 'nba.com' not in pdf_url:
                self.send_response(400)
                self.end_headers()
                return

            # Fetch the PDF
            req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                pdf_bytes = resp.read()

            pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')

            prompt = """Parse this NBA injury report PDF. Return ONLY a JSON object mapping team abbreviations to arrays of injured players.
Use standard NBA abbreviations (ATL, BOS, BKN, CHA, CHI, CLE, DAL, DEN, DET, GSW, HOU, IND, LAC, LAL, MEM, MIA, MIL, MIN, NOP, NYK, OKC, ORL, PHI, PHX, POR, SAC, SAS, TOR, UTA, WAS).
Only include players with status: Out, Doubtful, or Questionable. Exclude: Available, G League, Not With Team.
Format: {"DAL": [{"name": "Irving, Kyrie", "status": "out"}], "CHA": []}
Status values must be lowercase: out, doubtful, questionable.
Return only the JSON, no other text."""

            payload = json.dumps({
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 2000,
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'document', 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': pdf_b64}},
                        {'type': 'text', 'text': prompt}
                    ]
                }]
            }).encode('utf-8')

            api_req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': ANTHROPIC_API_KEY,
                    'anthropic-version': '2023-06-01'
                }
            )

            with urllib.request.urlopen(api_req, timeout=30) as resp:
                result = json.loads(resp.read())

            text = result['content'][0]['text'].strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()

            injury_data = json.loads(text)

            response_body = json.dumps(injury_data).encode('utf-8')
            self.send_response(200)
            self._cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        except Exception as e:
            print(f'Parse injuries error: {e}')
            self.send_response(500)
            self._cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

if __name__ == '__main__':
    server = HTTPServer(('localhost', 8000), ProxyHandler)
    print("Server running at http://localhost:8000")
    server.serve_forever()
