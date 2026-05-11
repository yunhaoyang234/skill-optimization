# Skill-V2

## System Commands

A sequence of NED velocity in meters per second, published at 1 FPS.

---

## Specifications

- **G(max_altitude < 10)**
- **G(linear_velocity <= 1)**
- **G(velocity_change <= 1)**
- **G(linear_velocity > 0 -> altitude > 0)**

---

## Skill: fly-in-square-shape-traj

**Global Contract:**
G(altitude < 10)
G(linear_velocity <= 1)
G(velocity_change <= 1)
G(linear_velocity > 0 -> altitude > 0)

**Local Contract:**
F (altitude > 0)
F (linear_velocity == 0 & altitude == 0)

**Semantic Contract:**

Proposition-aligned APIs:

```python
import math
from typing import Iterable, List, Tuple


Velocity = Tuple[float, float, float]


def _norm3(v: Velocity) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _clip_norm(v: Velocity, max_norm: float) -> Velocity:
    n = _norm3(v)
    if n == 0.0 or n <= max_norm:
        return v
    s = max_norm / n
    return (v[0] * s, v[1] * s, v[2] * s)


def _limit_delta(target: Velocity, previous: Velocity, max_delta: float) -> Velocity:
    delta = (
        target[0] - previous[0],
        target[1] - previous[1],
        target[2] - previous[2],
    )
    limited_delta = _clip_norm(delta, max_delta)

    return (
        previous[0] + limited_delta[0],
        previous[1] + limited_delta[1],
        previous[2] + limited_delta[2],
    )


def linear_velocity(v: Velocity) -> float:
    return _norm3(v)


def velocity_change(previous: Velocity, current: Velocity) -> float:
    return _norm3((
        current[0] - previous[0],
        current[1] - previous[1],
        current[2] - previous[2],
    ))


def _altitude_trace(plan: List[Velocity], initial_altitude: float = 0.0, 
        dt: float = 1.0) -> List[float]:
    trace = [initial_altitude]

    for _, _, vd in plan:
        z += vd * dt
        trace.append(z)

    return trace

def altitude(plan: List[Velocity], idx=-1) -> float:
    return _altitude_trace(plan)[idx]

def set_velocity(requested: Velocity, previous: Velocity) -> Velocity:
    speed_bounded = _clip_norm(requested, max_norm=1.0)
    return _limit_delta(speed_bounded, previous, max_delta=1.0)


def hold_position(previous: Velocity) -> Velocity:
    return set_velocity((0.0, 0.0, 0.0), previous)
```

Plan template:

```python
from typing import List, Tuple


Velocity = Tuple[float, float, float]


def generate_fly_in_square_shape_traj_plan(side_duration_s: int = 4,
    speed_mps: float = 0.5, final_altitude: float = 0.0) -> List[Velocity]:

    vel_traj: List[Velocity] = []
    ver_speed, vert_duration_s = 1, 10

    vel_traj += [(0.0, 0,0, -ver_speed)] * vert_duration_s  # take off
    vel_traj += [(0.0,  speed_mps, 0.0)] * side_duration_s  # east
    vel_traj += [(-speed_mps, 0.0, 0.0)] * side_duration_s  # south
    vel_traj += [(0.0, -speed_mps, 0.0)] * side_duration_s  # west
    vel_traj += [( speed_mps, 0.0, 0.0)] * side_duration_s  # north
    vel_traj += [(0.0,  0,0, ver_speed)] * vert_duration_s  # land
    
    plan: List[Velocity] = []
    previous: Velocity = (0.0, 0.0, 0.0)
    for requested in vel_traj:
        safe_cmd = set_velocity(requested, previous)
        plan.append(safe_cmd)
        previous = safe_cmd

    stop_cmd = hold_position(previous)
    plan.append(stop_cmd)

    return plan


plan: List[Velocity] = generate_fly_in_square_shape_traj_plan()

# Example output shape:
# [
#   (0.5, 0.0, 0.0),
#   (0.5, 0.0, 0.0),
#   ...
#   (0.0, -0.5, 0.0),
#   (0.0, 0.0, 0.0),
# ]
```

