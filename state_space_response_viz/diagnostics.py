"""Parse the controller's ``~/diagnostics`` Float64MultiArray.

The Kontrol'Em controllers (``kontrolem_controllers_base``) publish a flat
``std_msgs/Float64MultiArray`` every update when ``publish_diagnostics`` is on.
The message is self-describing: ``layout.dim`` lists one entry per field
section (``label``/``size``) in wire order, so this parser slices the flat
``data`` array by walking the layout — it never hard-codes offsets. See
``docs/runtime/diagnostics.md`` for the section table.

Sections (in order): ``time``[1] · ``timing``[period_s, update_us, rate_hz,
deadline_miss] · ``flags``[valid, safe_action_code] · ``x``[absolute q then
qdot, 2n] · ``ref``[reference interfaces, absolute] · ``err``[law tracking
error] · ``u``[command, m] · ``xhat``[observer state, 0 for static gain].
"""

from typing import Dict, List

SAFE_ACTIONS = {0: 'hold_u_eq', 1: 'zero_command', 2: 'deactivate'}


def split_sections(layout) -> Dict[str, slice]:
    """Map each ``layout.dim`` label to its slice into the flat data array."""
    out: Dict[str, slice] = {}
    off = 0
    for dim in layout.dim:
        size = int(dim.size)
        out[dim.label] = slice(off, off + size)
        off += size
    return out


def parse(msg) -> Dict[str, object]:
    """Turn one Float64MultiArray into a structured, JSON-friendly frame.

    Returns a dict with the decoded sections plus derived scalars. Raises
    ValueError if the layout is missing (an unlabeled array is not ours).
    """
    if not msg.layout.dim:
        raise ValueError('diagnostics message has no layout.dim — not a '
                         'Kontrol\'Em diagnostics array')
    data = list(msg.data)
    sec = split_sections(msg.layout)

    def block(name: str) -> List[float]:
        s = sec.get(name)
        return [float(v) for v in data[s]] if s is not None else []

    timing = block('timing')
    flags = block('flags')
    frame = {
        't': block('time')[0] if sec.get('time') else 0.0,
        'x': block('x'),
        'ref': block('ref'),
        'err': block('err'),
        'u': block('u'),
        'xhat': block('xhat'),
        'period_s': timing[0] if len(timing) > 0 else 0.0,
        'update_us': timing[1] if len(timing) > 1 else 0.0,
        'rate_hz': timing[2] if len(timing) > 2 else 0.0,
        'deadline_miss': bool(timing[3]) if len(timing) > 3 else False,
        'valid': bool(flags[0]) if len(flags) > 0 else True,
        'safe_action': SAFE_ACTIONS.get(int(flags[1]) if len(flags) > 1 else 0,
                                        'hold_u_eq'),
    }
    return frame


def section_sizes(layout) -> Dict[str, int]:
    """Label -> element count, for advertising which panels have data."""
    return {dim.label: int(dim.size) for dim in layout.dim}
