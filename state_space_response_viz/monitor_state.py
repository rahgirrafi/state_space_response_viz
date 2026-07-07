"""Thread-safe hand-off between the ROS callbacks and the Flask server.

Kept ROS-free so it (and the SSE snapshot logic) can be unit-tested without a
running middleware. The node writes frames/metrics from the executor thread;
the server reads incremental snapshots from the Flask thread.
"""

import collections
import threading
import time
from typing import Dict


class MonitorState:
    def __init__(self, window_seconds: float, controller: str,
                 clock=time.monotonic):
        self._lock = threading.Lock()
        self._clock = clock
        self.window_seconds = float(window_seconds)
        self._frames: 'collections.deque[dict]' = collections.deque()
        self._seq = 0
        self._meta = {
            'controller': controller,
            'has_diag': False,
            'joint_names': [],
            'sections': {},           # label -> size
            'safe_action': 'hold_u_eq',
        }
        self._meta_rev = 0
        self._metrics: Dict = {}

    # -- writers (ROS thread) ----------------------------------------------
    def update_meta(self, **kw) -> None:
        with self._lock:
            changed = False
            for k, v in kw.items():
                if self._meta.get(k) != v:
                    self._meta[k] = v
                    changed = True
            if changed:
                self._meta_rev += 1

    def push_frame(self, frame: dict) -> None:
        now = self._clock()
        with self._lock:
            self._seq += 1
            frame['seq'] = self._seq
            frame['_wall'] = now
            self._frames.append(frame)
            horizon = now - self.window_seconds
            while self._frames and self._frames[0]['_wall'] < horizon:
                self._frames.popleft()

    def set_metrics(self, m: Dict) -> None:
        with self._lock:
            self._metrics = m

    # -- readers (Flask thread) --------------------------------------------
    def window_arrays(self):
        """(t list, frames list) snapshot for metric computation."""
        with self._lock:
            frames = list(self._frames)
        return [f['t'] for f in frames], frames

    def snapshot_since(self, cursor: int) -> Dict:
        """New frames (seq > cursor) plus current metrics/meta for the SSE feed."""
        with self._lock:
            new = [self._strip(f) for f in self._frames if f['seq'] > cursor]
            last = self._frames[-1]['seq'] if self._frames else cursor
            return {
                'frames': new,
                'cursor': last,
                'metrics': dict(self._metrics),
                'meta': dict(self._meta),
                'meta_rev': self._meta_rev,
            }

    def meta(self) -> Dict:
        with self._lock:
            return dict(self._meta)

    @staticmethod
    def _strip(f: dict) -> dict:
        return {k: v for k, v in f.items() if k != '_wall'}
