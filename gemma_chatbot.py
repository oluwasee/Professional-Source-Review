import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openai import OpenAI


HOST = "127.0.0.1"
PORT = 1235
MODEL = "google/gemma-4-e4b"
LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Gemma Chatbot</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #f1f5f9; color: #172033; }
    main { max-width: 760px; margin: 40px auto; padding: 0 16px; }
    section { background: white; border: 1px solid #dbe2ea; border-radius: 12px; overflow: hidden; }
    header { padding: 20px 24px; border-bottom: 1px solid #e5e7eb; }
    h1 { margin: 0 0 4px; font-size: 1.35rem; }
    .model { color: #64748b; font-size: .9rem; }
    #messages { min-height: 420px; max-height: 58vh; overflow-y: auto; padding: 20px; }
    .message { margin: 0 0 16px; white-space: pre-wrap; line-height: 1.5; }
    .label { display: block; margin-bottom: 4px; font-size: .78rem; font-weight: 700; color: #64748b; text-transform: uppercase; }
    .user { color: #1d4ed8; }
    .assistant { color: #172033; }
    form { display: flex; gap: 10px; padding: 16px; border-top: 1px solid #e5e7eb; }
    textarea { flex: 1; resize: vertical; min-height: 44px; padding: 11px; border: 1px solid #cbd5e1; border-radius: 8px; font: inherit; }
    button { border: 0; border-radius: 8px; padding: 0 18px; background: #1d4ed8; color: white; font: inherit; cursor: pointer; }
    button:disabled { opacity: .55; cursor: wait; }
    #status { min-height: 1.2em; padding: 0 20px 14px; color: #b91c1c; font-size: .9rem; }
  </style>
</head>
<body>
  <main>
    <section>
      <header><h1>Gemma Chatbot</h1><div class="model">Model: google/gemma-4-e4b</div></header>
      <div id="messages"></div>
      <div id="status"></div>
      <form id="chat-form">
        <textarea id="prompt" placeholder="Ask Gemma something..." required></textarea>
        <button id="send" type="submit">Send</button>
      </form>
    </section>
  </main>
  <script>
    const messages = [];
    const list = document.querySelector('#messages');
    const form = document.querySelector('#chat-form');
    const prompt = document.querySelector('#prompt');
    const send = document.querySelector('#send');
    const status = document.querySelector('#status');

    function addMessage(role, content) {
      messages.push({ role, content });
      const item = document.createElement('p');
      item.className = `message ${role}`;
      const label = document.createElement('span');
      label.className = 'label';
      label.textContent = role === 'user' ? 'You' : 'Gemma';
      item.append(label, document.createTextNode(content));
      list.append(item);
      list.scrollTop = list.scrollHeight;
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const content = prompt.value.trim();
      if (!content) return;
      addMessage('user', content);
      prompt.value = '';
      send.disabled = true;
      status.textContent = '';
      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'The request failed.');
        addMessage('assistant', data.message);
      } catch (error) {
        status.textContent = error.message;
      } finally {
        send.disabled = false;
        prompt.focus();
      }
    });
  </script>
</body>
</html>"""


class ChatHandler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_json({"error": "Not found."}, 404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            messages = payload["messages"]
            if not messages or messages[-1].get("role") != "user":
                raise ValueError("A user message is required.")

            client = OpenAI(base_url=LM_STUDIO_BASE_URL, api_key="lm-studio")
            completion = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=512,
            )
            self.send_json({"message": completion.choices[0].message.content})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, 400)
        except Exception as error:
            self.send_json({"error": f"Model request failed: {error}"}, 502)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), ChatHandler)
    print(f"Gemma chatbot running at http://{HOST}:{PORT}")
    print(f"Using LM Studio at {LM_STUDIO_BASE_URL}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping chatbot.")
    finally:
        server.server_close()