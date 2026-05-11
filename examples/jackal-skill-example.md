## APIs

```Python
def velocity_publisher(linear, angular):
    # sends linear and angular velocity commands
    
def yolo_listener(object)->bool:
    # receives visual observations from an OOD
```

---

## Specifications

- **G(people observed → X stop)**
- **G(obstacle observed → X ¬ forward)**
- **G(speed < 0.5)**

---

## Skill: drive

**Global Contract:**
G(people observed → X stop)
G(obstacle observed → X ¬ forward)
G(speed < 0.5)

**Local Contract:**
F ¬people observed & ¬obstacle observed → F ¬stop

**Semantic Contract:**

Proposition-aligned APIs:

```python
MAX_SPEED = 0.5
CURRENT_SPEED = 0.0
def people_observed() -> bool:
    return yolo_listener("people")
def obstacle_observed() -> bool:
    return yolo_listener("obstacle")
def speed() -> float:
    return CURRENT_SPEED

def set_velocity(linear: float, angular: float) -> None:
    global CURRENT_SPEED
    CURRENT_SPEED = abs(linear)
    velocity_publisher(linear=linear, angular=angular)
    
def forward() -> None:
    set_velocity(linear=0.3, angular=0.0)
def backward() -> None:
    set_velocity(linear=-0.3, angular=0.0)
def stop() -> None:
    set_velocity(linear=0.0, angular=0.0)
def turn_left() -> None:
    set_velocity(linear=0.0, angular=0.5)

def turn_right() -> None:
    set_velocity(linear=0.0, angular=-0.5)
```

Plan template:

```python
while True:
    if people_observed():
        stop()
    elif obstacle_observed():
        stop()
        # alternatively:
        # turn_left()
        # turn_right()
    else:
        forward()
```

## Skill: find-object

**Semantic Contract:**

Proposition-aligned APIs:

```python
MAX_SPEED = 0.5
CURRENT_SPEED = 0.0
def people_observed() -> bool:
    return yolo_listener("people")
def obstacle_observed() -> bool:
    return yolo_listener("obstacle")
def target_observed(target) -> bool:
    return yolo_listener(target)
def speed() -> float:
    return CURRENT_SPEED

def set_velocity(linear: float, angular: float) -> None:
    global CURRENT_SPEED
    CURRENT_SPEED = abs(linear)
    velocity_publisher(linear=linear, angular=angular)
    
def forward() -> None:
    set_velocity(linear=0.3, angular=0.0)
def backward() -> None:
    set_velocity(linear=-0.3, angular=0.0)
def stop() -> None:
    set_velocity(linear=0.0, angular=0.0)
def turn_left() -> None:
    set_velocity(linear=0.0, angular=0.5)

def turn_right() -> None:
    set_velocity(linear=0.0, angular=-0.5)
```

Plan template:

```python
while True:
    if people_observed():
        stop()
    elif obstacle_observed():
        turn_right()
    elif object_observed():
        stop()
        break
    else:
        forward()
```

## Skill: bypass-object

**Semantic Contract:**

Proposition-aligned APIs:

```python
MAX_SPEED = 0.5
CURRENT_SPEED = 0.0
def people_observed() -> bool:
    return yolo_listener("people")
def obstacle_observed() -> bool:
    return yolo_listener("obstacle")
def object_observed(target) -> bool:
    return yolo_listener(object)
def speed() -> float:
    return CURRENT_SPEED

def set_velocity(linear: float, angular: float) -> None:
    global CURRENT_SPEED
    CURRENT_SPEED = abs(linear)
    velocity_publisher(linear=linear, angular=angular)
    
def forward() -> None:
    set_velocity(linear=0.3, angular=0.0)
def backward() -> None:
    set_velocity(linear=-0.3, angular=0.0)
def stop() -> None:
    set_velocity(linear=0.0, angular=0.0)
def turn_left() -> None:
    set_velocity(linear=0.0, angular=0.5)

def turn_right() -> None:
    set_velocity(linear=0.0, angular=-0.5)
```

Plan template:

```python
while True:
    if people_observed():
        stop()
    elif obstacle_observed() 
            or object_observed():
        turn_right()
    else:
        forward()
```

