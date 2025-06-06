# Author(s): Dr. Patrick Lemoine

# DRAFT PROJECT TWISTER COLLISION AND FUSION
# This is just a draft, there is still lots of things to do to have a realistic result. 
# So follow me ...

from ursina import *
import numpy as np

app = Ursina()

# ----------- Terrain Generation -----------
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

def get_terrain_height(x, z):
    i = int(np.clip(x/scale, 0, size-1))
    j = int(np.clip(z/scale, 0, size-1))
    return heightmap[i, j]

# ----------- Tornado Class -----------
class Tornado(Entity):
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
                 color1=color.azure,
                 color2=color.orange,
                 wind_speed=Vec3(0,0,0),
                 collider_radius=3.5,
                 fusion=False,
                 fusion_progress=0.0,
                 fusion_target=None,
                 particles_data=None):
        super().__init__(
            position=position,
            model='sphere',
            scale=collider_radius*2,
            color=color.clear,
            collider='sphere'
        )
        
        self.n_particles = n_particles
        self.height = height
        self.radius_base = radius_base
        self.radius_top = radius_top
        self.core_radius = core_radius
        self.omega0 = omega0
        self.max_inclination = max_inclination
        self.sin_amplitude = sin_amplitude
        self.sin_freq = sin_freq
        self.color1 = color1
        self.color2 = color2
        self.wind_speed = wind_speed
        self.collider_radius = collider_radius
        self.fusion = fusion
        self.fusion_progress = fusion_progress
        self.fusion_target = fusion_target
        self.particles = []
        if particles_data is None:
            self.init_particles()
        else:
            self.particles_from_data(particles_data)
        self.v_theta_max = self.get_vortex_velocity(self.radius_top)
        self.v_up_max = 1.5
        self.v_tot_max = np.sqrt(self.v_theta_max**2 + self.v_up_max**2)

    def get_vortex_velocity(self, r):
        if r < self.core_radius:
            return self.omega0 * r
        else:
            return self.omega0 * self.core_radius**2 / r

    def init_particles(self):
        for i in range(self.n_particles):
            z = np.random.power(2.5) * self.height
            r = self.radius_base + (self.radius_top - self.radius_base) * (z / self.height)**1.5
            theta = np.random.uniform(0, 2 * np.pi)
            col = self.color1 if i < self.n_particles//2 else self.color2
            p = Entity(model='sphere', color=col, scale=lerp(0.05, 0.18, z/self.height), position=(0, z, 0), alpha=lerp(0.7, 0.4, z/self.height))
            self.particles.append({'entity': p, 'r': r, 'theta': theta, 'z': z, 'col': col})

    def particles_from_data(self, data):
        for d in data:
            p = Entity(model='sphere', color=d['col'], scale=lerp(0.05, 0.18, d['z']/self.height), position=(0, d['z'], 0), alpha=lerp(0.7, 0.4, d['z']/self.height))
            self.particles.append({'entity': p, 'r': d['r'], 'theta': d['theta'], 'z': d['z'], 'col': d['col']})

    def update_particles(self):
        if self.fusion and self.fusion_target is not None:
            self.fusion_progress = min(self.fusion_progress + time.dt * 0.5, 1.0)
            self.position = lerp(self.position, self.fusion_target['position'], self.fusion_progress)
            self.height = lerp(self.height, self.fusion_target['height'], self.fusion_progress)
            self.radius_base = lerp(self.radius_base, self.fusion_target['radius_base'], self.fusion_progress)
            self.radius_top = lerp(self.radius_top, self.fusion_target['radius_top'], self.fusion_progress)
            self.core_radius = lerp(self.core_radius, self.fusion_target['core_radius'], self.fusion_progress)
            self.omega0 = lerp(self.omega0, self.fusion_target['omega0'], self.fusion_progress)
            self.max_inclination = lerp(self.max_inclination, self.fusion_target['max_inclination'], self.fusion_progress)
            self.sin_amplitude = lerp(self.sin_amplitude, self.fusion_target['sin_amplitude'], self.fusion_progress)
            self.sin_freq = lerp(self.sin_freq, self.fusion_target['sin_freq'], self.fusion_progress)
            self.collider_radius = lerp(self.collider_radius, self.fusion_target['collider_radius'], self.fusion_progress)
            self.scale = self.collider_radius*2
        base_y = get_terrain_height(self.x, self.z) + 0.2
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
            x = self.x + x_axis + part['r'] * np.cos(part['theta'])
            y = base_y + part['z']
            z_pos = self.z + z_axis + part['r'] * np.sin(part['theta'])

            part['entity'].color = part['col']
            part['entity'].position = (x, y, z_pos)
            #part['entity'].scale = lerp(0.05, 0.18, part['z']/self.height)
            part['entity'].scale = lerp(0.2, 0.38, part['z']/self.height)
            part['entity'].alpha = lerp(0.9, 0.4, part['z']/self.height)

# ----------- Camera Setup -----------
editor_camera = EditorCamera()
editor_camera.position = Vec3(size*scale//2, 10, -30)
editor_camera.look_at(Vec3(0, 0, 0))


# ----------- Tornade fusion -----------
tornadoes = []
t1 = Tornado(position=(size*scale*0.1, 0, size*scale*0.5), 
             n_particles=900, 
             height=20, 
             radius_base=0.25, 
             radius_top=2.0, 
             core_radius=0.6, 
             omega0=7.0, 
             max_inclination=4.5, 
             sin_amplitude=0.5, 
             sin_freq=2.5, 
             color1=color.azure, 
             color2=color.cyan,
             wind_speed=Vec3(0.03, 0, -0.00),
             collider_radius=3.2)

t2 = Tornado(position=(size*scale*0.9, 0, size*scale*0.5), 
             n_particles=1900, 
             height=25, 
             radius_base=0.9, 
             radius_top=9.2, 
             core_radius=3.0, 
             omega0=15.5, 
             max_inclination=10.0, 
             sin_amplitude=0.7, 
             sin_freq=3.0, 
             color1=color.orange, 
             color2=color.red,
             wind_speed=Vec3(-0.19, 0, 0.00),
             collider_radius=3.5)


tornadoes += [t1, t2]
fusion_phase = False
fusion_timer = 0
fusion_duration = 100.0  # secondes

# ----------- Mini-map and update parts  -----------
mini_grid_step = 2.0
mini_grid_x = np.arange(2, size*scale-2, mini_grid_step)
mini_grid_z = np.arange(2, size*scale-2, mini_grid_step)
mini_arrows = []

def compute_wind_at_point(point, tornadoes):
    wind = Vec3(0,0,0)
    for t in tornadoes:
        rel = Vec3(point.x - t.x, 0, point.z - t.z)
        r = rel.length()
        if r < 1e-2:
            continue
        if r < t.core_radius:
            v_theta = t.omega0 * r
        else:
            v_theta = t.omega0 * (t.core_radius**2) / r
        tangent = Vec3(-rel.z, 0, rel.x).normalized()
        wind += tangent * v_theta + t.wind_speed
    return wind

# Overlay mini-map parent (UI)
mini_map_parent = Entity(parent=camera.ui, enabled=True)
mini_map_bg = Entity(parent=mini_map_parent, model='quad', scale=(0.92,0.92), position=(0.68,0.68,0), color=color.rgba(0,0,0,0.5), eternal=True)


def update_minimap():
    for arr in mini_arrows:
        destroy(arr)
    mini_arrows.clear()
    dpx = 0.254
    dpy = 0.225
    # Flèches de vent
    for gx in mini_grid_x:
        for gz in mini_grid_z:
            wind = compute_wind_at_point(Vec3(gx,0,gz), tornadoes)
            norm = wind.length()
            if norm < 1e-3:
                wind = Vec3(0,0,1)
            else:
                wind = wind.normalized()
            px = (gx/(size*scale)) * 0.28 + dpx
            pz = (gz/(size*scale)) * 0.28 + dpy
            arrow = Entity(parent=mini_map_parent, model='quad', scale=(0.003,0.009), position=(px,pz,-0.01), color=color.yellow)
            angle = np.degrees(np.arctan2(wind.x, wind.z))
            arrow.rotation_z = -angle
            mini_arrows.append(arrow)
            dot = Entity(parent=mini_map_parent, model='circle', scale=0.002, position=(px,pz,-0.01), color=color.green)
            mini_arrows.append(dot)
    # Points rouges pour les tornades
    for t in tornadoes:
        px = (t.x/(size*scale)) * 0.28 + dpx
        pz = (t.z/(size*scale)) * 0.28 + dpy
        dot = Entity(parent=mini_map_parent, model='circle', scale=0.018, position=(px,pz,-0.01), color=color.red)
        mini_arrows.append(dot)


# ----------- Update All -----------
def update():
    global fusion_phase, fusion_timer
    if not fusion_phase and len(tornadoes) == 2:
        t1, t2 = tornadoes
        t1.position += t1.wind_speed
        t2.position += t2.wind_speed
        if t1.intersects(t2).hit:
            fusion_phase = True
            fusion_timer = 0
            fusion_target = {
                'position': (t1.position + t2.position)/2,
                'height': (t1.height + t2.height)/2,
                'radius_base': (t1.radius_base + t2.radius_base)/2,
                'radius_top': (t1.radius_top + t2.radius_top)*0.7,
                'core_radius': (t1.core_radius + t2.core_radius)/2,
                'omega0': (t1.omega0 + t2.omega0)/2,
                'max_inclination': (t1.max_inclination + t2.max_inclination)/2,
                'sin_amplitude': (t1.sin_amplitude + t2.sin_amplitude)/2,
                'sin_freq': (t1.sin_freq + t2.sin_freq)/2,
                'collider_radius': (t1.collider_radius + t2.collider_radius)/1.5
            }
            t1.fusion = True
            t2.fusion = True
            t1.fusion_target = fusion_target
            t2.fusion_target = fusion_target
            t1.wind_speed = (fusion_target['position'] - t1.position) / fusion_duration
            t2.wind_speed = (fusion_target['position'] - t2.position) / fusion_duration
    elif fusion_phase and len(tornadoes) == 2:
        t1, t2 = tornadoes
        fusion_timer += time.dt
        t1.position += t1.wind_speed * time.dt
        t2.position += t2.wind_speed * time.dt
        t1.update_particles()
        t2.update_particles()
        if fusion_timer > fusion_duration:
            pos1 = t1.position
            pos2 = t2.position
            all_particles = []
            for p in t1.particles + t2.particles:
                all_particles.append({'r': p['r'], 'theta': p['theta'], 'z': p['z'], 'col': p['col']})
                destroy(p['entity'])
            destroy(t1)
            destroy(t2)
            tornadoes.clear()
            tornadoes.append(Tornado(
                position=(pos1 + pos2)/2,
                n_particles=len(all_particles),
                height=t1.fusion_target['height'],
                radius_base=t1.fusion_target['radius_base'],
                radius_top=t1.fusion_target['radius_top'],
                core_radius=t1.fusion_target['core_radius'],
                omega0=t1.fusion_target['omega0'],
                max_inclination=t1.fusion_target['max_inclination'],
                sin_amplitude=t1.fusion_target['sin_amplitude'],
                sin_freq=t1.fusion_target['sin_freq'],
                color1=t1.color1,
                color2=t2.color1,
                wind_speed=Vec3(0,0,0),
                collider_radius=t1.fusion_target['collider_radius'],
                fusion=False,
                particles_data=all_particles
            ))
            fusion_phase = False
            return
    for t in tornadoes:
        t.update_particles()
    update_minimap()

app.run()

