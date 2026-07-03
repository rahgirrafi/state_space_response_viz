"""PlaybackClock: fake wall clocks, no sleeping tests."""

import pytest

from state_space_response_viz.playback import (
    PAUSED, PLAYING, STOPPED, PlaybackClock)


def test_initial_state_is_stopped_at_t0():
    c = PlaybackClock(5.0)
    assert c.state == STOPPED
    assert c.now(123.0) == 0.0


def test_play_advances_with_wall_time():
    c = PlaybackClock(5.0)
    c.play(wall=100.0)
    assert c.state == PLAYING
    assert c.now(101.5) == pytest.approx(1.5)


def test_pause_freezes_and_play_resumes():
    c = PlaybackClock(5.0)
    c.play(100.0)
    c.pause(102.0)
    assert c.state == PAUSED
    assert c.now(110.0) == pytest.approx(2.0)     # frozen
    c.play(110.0)
    assert c.now(111.0) == pytest.approx(3.0)     # resumes, no jump


def test_speed_change_rebases_without_jump():
    c = PlaybackClock(10.0)
    c.play(100.0)
    assert c.now(102.0) == pytest.approx(2.0)
    c.set_speed(0.5, wall=102.0)
    assert c.now(102.0) == pytest.approx(2.0)     # no jump at the change
    assert c.now(104.0) == pytest.approx(3.0)     # then half rate


def test_pause_speed_play_sequence():
    """The pitfall-9 sequence: pause -> change speed -> play."""
    c = PlaybackClock(10.0)
    c.play(100.0)
    c.pause(101.0)
    c.set_speed(2.0, wall=105.0)
    c.play(105.0)
    assert c.now(106.0) == pytest.approx(3.0)     # 1.0 + 2.0*1s


def test_seek_while_playing_and_paused():
    c = PlaybackClock(10.0)
    c.play(100.0)
    c.seek(7.0, wall=101.0)
    assert c.state == PLAYING
    assert c.now(102.0) == pytest.approx(8.0)
    c.pause(102.0)
    c.seek(1.0, wall=102.0)
    assert c.state == PAUSED
    assert c.now(200.0) == pytest.approx(1.0)


def test_seek_clamps_to_span():
    c = PlaybackClock(5.0)
    c.seek(99.0, wall=0.0)
    assert c.now(0.0) == 5.0
    c.seek(-99.0, wall=0.0)
    assert c.now(0.0) == 0.0


def test_end_of_trajectory_stops():
    c = PlaybackClock(5.0)
    c.play(100.0)
    assert c.now(104.0) == pytest.approx(4.0)
    assert c.now(120.0) == 5.0
    assert c.state == STOPPED
    assert c.now(130.0) == 5.0                    # stays at the end


def test_play_after_end_restarts():
    c = PlaybackClock(5.0)
    c.play(100.0)
    c.now(120.0)                                  # runs off the end
    c.play(200.0)
    assert c.now(201.0) == pytest.approx(1.0)


def test_loop_wraps():
    c = PlaybackClock(5.0, loop=True)
    c.play(100.0)
    assert c.now(107.0) == pytest.approx(2.0)     # 7 mod 5
    assert c.state == PLAYING
    assert c.now(108.0) == pytest.approx(3.0)     # keeps running after wrap


def test_nonzero_t0():
    c = PlaybackClock(4.0, t0=1.0)
    assert c.now(0.0) == 1.0
    c.play(100.0)
    assert c.now(102.0) == pytest.approx(3.0)
    assert c.now(110.0) == 5.0                    # t0 + duration


def test_reset():
    c = PlaybackClock(5.0)
    c.play(100.0)
    c.now(102.0)
    c.reset()
    assert c.state == STOPPED and c.now(200.0) == 0.0


def test_invalid_speed_rejected():
    c = PlaybackClock(5.0)
    with pytest.raises(ValueError, match='speed'):
        c.set_speed(0.0, wall=0.0)
    with pytest.raises(ValueError, match='speed'):
        PlaybackClock(5.0, speed=1000.0)


def test_invalid_duration_rejected():
    with pytest.raises(ValueError, match='duration'):
        PlaybackClock(0.0)
