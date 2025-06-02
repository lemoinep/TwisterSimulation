from ursina import *
import numpy as np

app = Ursina()

# ----------- Terrain Mesh Generation (Heightmap) -----------
size = 64
scale = 0.7
height_scale = 0.8

# Create a 2D grid and generate a heightmap using a sinusoidal function
x = np.linspace(0, 4*np.pi, size)
y = np.linspace(0, 4*np.pi, size)
xx, yy = np.meshgrid(x, y)
heightmap = (np.sin(xx) * np.cos(yy)) * height_scale  # Simulates terrain elevation

vertices = []
uvs = []
for i in range(size):
    for j in range(size):
        vertices.append((i*scale, heightmap[i,j], j*scale))
        uvs.append((i/(size-1), j/(size-1)))

triangles = []
for i in range(size-1):
    for j in range(size-1):
        idx = i*size + j
        # Each quad is split into two triangles
        triangles += [idx, idx+1, idx+size]
        triangles += [idx+1, idx+size+1, idx+size]

terrain_mesh = Mesh(vertices=vertices, triangles=triangles, uvs=uvs, mode='line')
terrain = Entity(model=terrain_mesh, color=color.gray)

# ----------- Tornado Parameters -----------
n_particles = 2500  # Number of particles representing the tornado
height = 20         # Vertical extent of the tornado
radius_base = 0.25  # Tornado radius at the base (ground level)
radius_top = 3.0    # Tornado radius at the top (altitude = height)
core_radius = 1.6   # Radius of the solid-body rotating core
omega0 = 7.0        # Angular velocity at the core (rad/s)
max_inclination = 10.0  # Maximum horizontal displacement (tornado tilt)
sin_amplitude = 0.5     # Amplitude of the tornado's sinusoidal oscillation
sin_freq = 2.5          # Frequency of the oscillation

# Tornado initial position and wind speed (for movement)
tornado_pos = Vec3(size*scale//4, 0, size*scale//2)
wind_speed = Vec3(0.04, 0, -0.02)

particles = []
debris_particles = []

# ----------- Tornado Particle Initialization -----------
for i in range(n_particles):
    # Particle vertical position: power law distribution for more particles near the ground
    z = np.random.power(2.5) * height
    # Radial position increases with height, with some randomness
    r = radius_base + (radius_top - radius_base) * (z / height)**1.5 + np.random.uniform(0, 5.5)
    theta = np.random.uniform(0, 2 * np.pi)
    # Each particle is an entity (sphere) whose size and transparency depend on altitude
    p = Entity(model='sphere', color=color.gray, scale=lerp(0.05, 0.18, z/height), position=(0, z, 0), alpha=lerp(0.7, 0.4, z/height))
    particles.append({'entity': p, 'r': r, 'theta': theta, 'z': z})

# ----------- Debris Particle Initialization (larger objects) -----------
for i in range(100):
    angle = np.random.uniform(0, 2*np.pi)
    radius = np.random.uniform(radius_base*0.7, radius_base*5.6)
    x = radius * np.cos(angle)
    y = np.random.uniform(0, 0.3)
    z_pos = radius * np.sin(angle)
    d = Entity(model='sphere', color=color.black, scale=0.12, position=(x, y, z_pos), alpha=0.7)
    debris_particles.append({'entity': d, 'angle': angle, 'radius': radius})

# ----------- Camera Initial Positioning -----------
editor_camera = EditorCamera()
editor_camera.position = Vec3(size*scale//2, 10, -30)
editor_camera.look_at(Vec3(0, 0, 0))

# ----------- Physical Model: Tornado Vortex Velocity Profile -----------
def get_vortex_velocity(r, core_radius, omega0):
    """
    Returns the tangential velocity at radius r in the tornado.
    - For r < core_radius: solid body rotation (v ∝ r)
    - For r >= core_radius: Rankine vortex (v ∝ 1/r)
    """
    if r < core_radius:
        v_theta = omega0 * r
    else:
        v_theta = omega0 * core_radius**2 / r
    return v_theta

def get_terrain_height(x, z):
    """
    Returns the terrain height at position (x, z) by sampling the heightmap.
    """
    i = int(np.clip(x/scale, 0, size-1))
    j = int(np.clip(z/scale, 0, size-1))
    return heightmap[i, j]

# Maximum velocities for color mapping
v_theta_max = get_vortex_velocity(radius_top, core_radius, omega0)
v_up_max = 1.5  # Maximum upward velocity (vertical wind)
v_tot_max = np.sqrt(v_theta_max**2 + v_up_max**2)

# ----------- Main Update Loop -----------
def update():
    global tornado_pos
    # Move tornado horizontally according to wind speed
    tornado_pos += wind_speed
    tornado_pos.x = np.clip(tornado_pos.x, 2, size*scale-2)
    tornado_pos.z = np.clip(tornado_pos.z, 2, size*scale-2)
    # The base of the tornado follows the terrain elevation
    base_y = get_terrain_height(tornado_pos.x, tornado_pos.z) + 0.2

    for part in particles:
        r = part['r']
        z = part['z']
        # Compute tangential velocity from vortex model
        v_theta = get_vortex_velocity(r, core_radius, omega0)
        # Updraft velocity decreases with radius (stronger in the core)
        v_up = lerp(2.0, 0.5, r/radius_top)
        # Update angular position (theta) and altitude (z)
        part['theta'] += time.dt * v_theta / (r + 1e-3)
        part['z'] += time.dt * v_up

        # If particle escapes the top, reset it near the ground
        if part['z'] > height:
            part['z'] = 0
            part['r'] = radius_base + (radius_top - radius_base) * (part['z'] / height)**1.5
            part['theta'] = np.random.uniform(0, 2 * np.pi)

        frac = part['z'] / height
        # Tornado tilt and oscillation (simulates realistic tornado motion)
        x_axis = max_inclination * frac
        z_axis = 0
        x_axis += sin_amplitude * np.sin(sin_freq * frac * np.pi + time.time())
        z_axis += sin_amplitude * np.cos(sin_freq * frac * np.pi + time.time() * 0.8)

        # Update radius as a function of height (tornado widens with altitude)
        part['r'] = radius_base + (radius_top - radius_base) * (part['z'] / height)**1.5
        x = tornado_pos.x + x_axis + part['r'] * np.cos(part['theta'])
        y = base_y + part['z']
        z_pos = tornado_pos.z + z_axis + part['r'] * np.sin(part['theta'])

        # Compute total velocity for color mapping
        v_tot = np.sqrt(v_theta**2 + v_up**2)
        t = np.clip(v_tot / v_tot_max, 0, 1)  # Normalize to [0,1]

        # Color gradient: higher velocity = deeper blue
        part['entity'].color = lerp(color.cyan, color.blue, t)
        part['entity'].position = (x, y, z_pos)
        part['entity'].scale = lerp(0.05, 0.18, part['z']/height)
        part['entity'].alpha = lerp(0.9, 0.4, part['z']/height)

    # Debris particles: rotate around the tornado base
    for d in debris_particles:
        d['angle'] += time.dt * 3.5
        d['entity'].x = tornado_pos.x + d['radius'] * np.cos(d['angle'])
        d['entity'].z = tornado_pos.z + d['radius'] * np.sin(d['angle'])
        d['entity'].y = base_y + np.random.uniform(0, 0.3)

app.run()


