"""PlaybackClock: the transport state machine, independent of ROS and UI.

Answers exactly one question — "what simulation time is it?" — as a pure
function of an injected wall-clock reading, so it is unit-testable with
fake clocks and shared conceptually with the JS twin in the setup
assistant. Every mutation (play, pause, seek, speed change) rebases the
(wall_anchor, sim_anchor) pair, so a speed change never makes the cursor
jump and dropped ticks never accumulate error.
"""

STOPPED = 'stopped'
PLAYING = 'playing'
PAUSED = 'paused'

SPEED_MIN = 0.01
SPEED_MAX = 10.0


class PlaybackClock:
    def __init__(self, duration: float, *, speed: float = 1.0,
                 loop: bool = False, t0: float = 0.0):
        if duration <= 0:
            raise ValueError('duration must be positive')
        self.t0 = float(t0)
        self.duration = float(duration)
        self.loop = bool(loop)
        self.state = STOPPED
        self._speed = self._check_speed(speed)
        self._wall_anchor = 0.0
        self._sim_anchor = self.t0

    @staticmethod
    def _check_speed(speed: float) -> float:
        speed = float(speed)
        if not SPEED_MIN <= speed <= SPEED_MAX:
            raise ValueError(
                f'speed must be in [{SPEED_MIN}, {SPEED_MAX}], got {speed}')
        return speed

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def t_end(self) -> float:
        return self.t0 + self.duration

    def now(self, wall: float) -> float:
        """Current simulation time; advances state on end-of-trajectory."""
        if self.state != PLAYING:
            return self._sim_anchor
        t = self._sim_anchor + self._speed * (wall - self._wall_anchor)
        if t < self.t_end:
            return t
        if self.loop:
            t = self.t0 + (t - self.t0) % self.duration
            self._rebase(wall, t)
            return t
        self.state = STOPPED
        self._sim_anchor = self.t_end
        return self.t_end

    def _rebase(self, wall: float, t_sim: float) -> None:
        self._wall_anchor = wall
        self._sim_anchor = min(max(t_sim, self.t0), self.t_end)

    def play(self, wall: float) -> None:
        if self.state == PLAYING:
            return
        # Restarting after reaching the end replays from the start.
        start = self.t0 if self._sim_anchor >= self.t_end else self._sim_anchor
        self._rebase(wall, start)
        self.state = PLAYING

    def pause(self, wall: float) -> None:
        if self.state == PLAYING:
            self._rebase(wall, self.now(wall))
            if self.state == PLAYING:   # now() may have hit the end
                self.state = PAUSED

    def reset(self) -> None:
        self.state = STOPPED
        self._sim_anchor = self.t0

    def seek(self, t_sim: float, wall: float) -> None:
        """Jump the cursor; playing stays playing, paused stays paused."""
        self._rebase(wall, t_sim)

    def set_speed(self, speed: float, wall: float) -> None:
        if self.state == PLAYING:
            self._rebase(wall, self.now(wall))
        self._speed = self._check_speed(speed)
