# Author(s): Dr. Patrick Lemoine

from ursina import *
import numpy as np

app = Ursina()

# ----------- Terrain Generation (heightmap) -----------
size = 64
scale = 0.7
height_scale = 0.8

x = np.linspace(0, 4*np.pi, size)
y = np.linspace(0, 4*np.pi, size)
xx, yy = np.meshgrid(x, y)
heightmap = (np.sin(xx) * np.cos(yy)) * height_scale

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
        triangles += [idx, idx+1, idx+size]
        triangles += [idx+1, idx+size+1, idx+size]

terrain_mesh = Mesh(vertices=vertices, triangles=triangles, uvs=uvs, mode='line')
terrain = Entity(model=terrain_mesh, color=color.gray)

# ----------- Tornado Class -----------
class Tornado:
    def __init__(self, 
                 position, 
                 n_particles=1000, 
                 height=20, 
                 radius_base=0.25, 
                 radius_top=2.0,
                 core_radius=0.6, 
                 omega0=7.0, 
                 max_inclination=4.5, 
                 sin_amplitude=0.5, 
                 sin_freq=2.5, 
                 color=color.azure, 
                 wind_speed=Vec3(0,0,0)):
        # Physical and geometric parameters
        self.position = Vec3(*position)
        self.n_particles = n_particles
        self.height = height
        self.radius_base = radius_base
        self.radius_top = radius_top
        self.core_radius = core_radius
        self.omega0 = omega0
        self.max_inclination = max_inclination
        self.sin_amplitude = sin_amplitude
        self.sin_freq = sin_freq
        self.color = color
        self.wind_speed = wind_speed

        self.particles = []
        self.debris_particles = []
        self.init_particles()
        self.init_debris()

        # For color mapping (velocity)
        self.v_theta_max = self.get_vortex_velocity(self.radius_top)
        self.v_up_max = 1.5
        self.v_tot_max = np.sqrt(self.v_theta_max**2 + self.v_up_max**2)

    def get_vortex_velocity(self, r):
        # Rankine vortex model: solid-body rotation in the core, potential vortex outside
        if r < self.core_radius:
            return self.omega0 * r
        else:
            return self.omega0 * self.core_radius**2 / r

    def init_particles(self):
        for _ in range(self.n_particles):
            z = np.random.power(2.5) * self.height
            r = self.radius_base + (self.radius_top - self.radius_base) * (z / self.height)**1.5
            theta = np.random.uniform(0, 2 * np.pi)
            p = Entity(model='sphere', color=self.color, scale=lerp(0.05, 0.18, z/self.height), position=(0, z, 0), alpha=lerp(0.7, 0.4, z/self.height))
            self.particles.append({'entity': p, 'r': r, 'theta': theta, 'z': z})

    def init_debris(self):
        for _ in range(80):
            angle = np.random.uniform(0, 2*np.pi)
            radius = np.random.uniform(self.radius_base*0.7, self.radius_base*5.6)
            x = radius * np.cos(angle)
            y = np.random.uniform(0, 0.3)
            z_pos = radius * np.sin(angle)
            d = Entity(model='sphere', color=color.black, scale=0.12, position=(x, y, z_pos), alpha=0.7)
            self.debris_particles.append({'entity': d, 'angle': angle, 'radius': radius})

    def get_terrain_height(self, x, z):
        i = int(np.clip(x/scale, 0, size-1))
        j = int(np.clip(z/scale, 0, size-1))
        return heightmap[i, j]

    def update(self):
        # Move tornado horizontally according to wind speed
        self.position += self.wind_speed
        self.position.x = np.clip(self.position.x, 2, size*scale-2)
        self.position.z = np.clip(self.position.z, 2, size*scale-2)
        base_y = self.get_terrain_height(self.position.x, self.position.z) + 0.2

        for part in self.particles:
            r = part['r']
            z = part['z']
            v_theta = self.get_vortex_velocity(r)
            v_up = lerp(2.0, 0.5, r/self.radius_top)
            part['theta'] += time.dt * v_theta / (r + 1e-3)
            part['z'] += time.dt * v_up

            if part['z'] > self.height:
                part['z'] = 0
                part['r'] = self.radius_base + (self.radius_top - self.radius_base) * (part['z'] / self.height)**1.5
                part['theta'] = np.random.uniform(0, 2 * np.pi)

            frac = part['z'] / self.height
            x_axis = self.max_inclination * frac
            z_axis = 0
            x_axis += self.sin_amplitude * np.sin(self.sin_freq * frac * np.pi + time.time())
            z_axis += self.sin_amplitude * np.cos(self.sin_freq * frac * np.pi + time.time() * 0.8)

            part['r'] = self.radius_base + (self.radius_top - self.radius_base) * (part['z'] / self.height)**1.5
            x = self.position.x + x_axis + part['r'] * np.cos(part['theta'])
            y = base_y + part['z']
            z_pos = self.position.z + z_axis + part['r'] * np.sin(part['theta'])

            # Compute total velocity for color mapping
            v_tot = np.sqrt(v_theta**2 + v_up**2)
            t = np.clip(v_tot / self.v_tot_max, 0, 1)
            part['entity'].color = lerp(color.cyan, color.blue, t)
            part['entity'].position = (x, y, z_pos)
            part['entity'].scale = lerp(0.05, 0.18, part['z']/self.height)
            part['entity'].alpha = lerp(0.9, 0.4, part['z']/self.height)

        for d in self.debris_particles:
            d['angle'] += time.dt * 3.5
            d['entity'].x = self.position.x + d['radius'] * np.cos(d['angle'])
            d['entity'].z = self.position.z + d['radius'] * np.sin(d['angle'])
            d['entity'].y = base_y + np.random.uniform(0, 0.3)

# ----------- Camera Setup -----------
editor_camera = EditorCamera()
editor_camera.position = Vec3(size*scale//2, 10, -30)
editor_camera.look_at(Vec3(0, 0, 0))

# ----------- Instantiate Multiple Tornadoes -----------
tornado1 = Tornado(position=(size*scale*0.3, 0, size*scale*0.5), 
                   n_particles=1200, 
                   height=20, 
                   radius_base=0.25, 
                   radius_top=2.0, 
                   core_radius=0.6, 
                   omega0=7.0, 
                   max_inclination=4.5, 
                   sin_amplitude=0.5, 
                   sin_freq=2.5, 
                   color=color.azure, 
                   wind_speed=Vec3(0.04, 0, -0.02))

tornado2 = Tornado(position=(size*scale*0.7, 0, size*scale*0.5), 
                   n_particles=900, 
                   height=25, 
                   radius_base=0.3, 
                   radius_top=3.2, 
                   core_radius=1.0, 
                   omega0=5.5, 
                   max_inclination=10.0, 
                   sin_amplitude=0.7, 
                   sin_freq=3.0, 
                   color=color.orange, 
                   wind_speed=Vec3(-0.03, 0, 0.01))

# ----------- Ursina Update Loop -----------
def update():
    tornado1.update()
    tornado2.update()

app.run()
