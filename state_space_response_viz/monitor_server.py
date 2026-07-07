"""Flask app for the live monitor: static dashboard + a Server-Sent-Events feed.

Same-origin, dependency-free (no CDN, no websocket lib) — mirrors the Flask +
static-JS pattern of ``state_space_setup_assistant``. ``/stream`` is an SSE
endpoint that pushes incremental sample batches from the shared
``MonitorState`` at a fixed rate; the browser keeps its own history and redraws.
"""

import json
import time

from flask import Flask, Response, jsonify, render_template, stream_with_context


def create_app(state, stream_rate: float = 25.0) -> Flask:
    app = Flask(__name__)
    interval = 1.0 / max(1.0, float(stream_rate))

    @app.get('/')
    def index():
        return render_template('monitor.html')

    @app.get('/info')
    def info():
        return jsonify(state.meta())

    @app.get('/stream')
    def stream():
        def gen():
            cursor = 0
            while True:
                snap = state.snapshot_since(cursor)
                cursor = snap['cursor']
                yield f'data: {json.dumps(snap)}\n\n'
                time.sleep(interval)

        return Response(
            stream_with_context(gen()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no',   # don't let a proxy buffer the stream
            })

    return app
