# Author(s): Dr. Patrick Lemoine

# Draft Project Twister Collision and Fusion With Artificial Intelligence
# This is just a draft, there is still lots of things to do to have a realistic result. 

# This Python code simulates a dynamic 3D environment with multiple tornadoes, 
# using the Ursina engine and NumPy for terrain and meteorological modeling. 
# The simulation features both player-controlled and AI-driven tornadoes,
# which move and interact according to atmospheric conditions and strategic behaviors. 
# The AI tornado actively pursues the player tornado, demonstrating 
# adaptive movement based on real-time simulation data. 
# Visual indicators, such as color-changing arrows on a mini-map, 
# display wind intensity and direction. The project also includes 
# robust collision and fusion handling for tornado interactions

# So follow me ...

from ursina import *
import numpy as np
import random

app = Ursina()
window.color = color.rgb(255,255,255)

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

def color_lerp(a, b, t):
    return color.rgb(
        int(a.r + (b.r - a.r) * t),
        int(a.g + (b.g - a.g) * t),
        int(a.b + (b.b - a.b) * t)
    )

class AtmosphericModel:
    def __init__(self, size):
        self.size = size
        self.pressure = np.full((size, size), 1000.0)
        self.temperature = np.full((size, size), 25.0)
        self.wind = np.zeros((size, size, 2))

    def update(self, tornadoes):
        self.pressure[:] = 1000.0
        self.temperature[:] = 25.0
        self.wind[:] = 0
        for t in tornadoes:
            cx, cz = int(t.position[0]//scale), int(t.position[2]//scale)
            for i in range(max(0, cx-8), min(self.size, cx+8)):
                for j in range(max(0, cz-8), min(self.size, cz+8)):
                    dist = np.sqrt((i-cx)**2 + (j-cz)**2)
                    if dist < 8:
                        self.pressure[i,j] -= t.intensity * 0.5 / (dist+1)
                        self.temperature[i,j] += t.intensity * 0.02 / (dist+1)
                        angle = np.arctan2(j-cz, i-cx)
                        self.wind[i,j,0] += np.cos(angle) * t.intensity * 0.1 / (dist+1)
                        self.wind[i,j,1] += np.sin(angle) * t.intensity * 0.1 / (dist+1)

    def get_local(self, x, z):
        ix, iz = int(x//scale), int(z//scale)
        ix = np.clip(ix, 0, self.size-1)
        iz = np.clip(iz, 0, self.size-1)
        return self.pressure[ix,iz], self.temperature[ix,iz], self.wind[ix,iz]

atmo = AtmosphericModel(size)

class Weather(Entity):
    def __init__(self):
        super().__init__()
        self.particles = []
        self.lightning_timer = 0

    def update_weather(self, tornadoes):
        for p in self.particles:
            p.y -= time.dt*random.uniform(8,12)
            if p.y < 0:
                p.x = random.uniform(0, size*scale)
                p.z = random.uniform(0, size*scale)
                p.y = random.uniform(10, 20)
        max_int = max([t.intensity for t in tornadoes]) if tornadoes else 0
        if len(self.particles) < int(200*max_int):
            for _ in range(5):
                p = Entity(model='cube', scale=(0.05,0.3,0.05), color=color.azure, position=(random.uniform(0, size*scale), random.uniform(10,20), random.uniform(0, size*scale)), enabled=True)
                self.particles.append(p)

weather = Weather()

class Tornado(Entity):
    def __init__(self, pos=(10,0,10), color_base=color.azure, color_top=color.white, intensity=1.0, ai_controlled=False):
        super().__init__()
        self.position = Vec3(*pos)
        self.intensity = intensity
        self.height = 8 + 2*intensity
        self.radius_base = 0.7 + 0.5*intensity
        self.radius_top = 2.0 + 1.5*intensity
        self.n_particles = 300 + int(200*intensity)
        self.particles = []
        self.color_base = color_base
        self.color_top = color_top
        self.angle = 0
        self.fusion = False
        self.fusion_target = None
        self.fusion_progress = 0
        self.ai_controlled = ai_controlled
        self.build_particles()

    def build_particles(self):
        self.particles.clear()
        for i in range(self.n_particles):
            h = random.uniform(0, self.height)
            r = self.radius_base + (self.radius_top-self.radius_base)*(h/self.height)
            theta = random.uniform(0, 2*np.pi)
            if i % 2 == 0:
                col = color_lerp(self.color_base, self.color_top, h/self.height)
            else:
                col = color_lerp(self.color_top, self.color_base, h/self.height)
            p = Entity(model='sphere', scale=0.15, color=col, position=(0,h,0), enabled=True)
            self.particles.append({'entity': p, 'h': h, 'r': r, 'theta': theta, 'col': col})

    def update(self):
        self.angle += time.dt * (1.5+self.intensity)
        for i, part in enumerate(self.particles):
            ent = part['entity']
            # Check that the entity is not destroyed
            if not ent or not hasattr(ent, 'enabled') or not ent.enabled or not ent._model or ent._model is None:
                continue
            h = part['h']
            r = self.radius_base + (self.radius_top-self.radius_base)*(h/self.height)
            theta = (i/self.n_particles)*2*np.pi + self.angle + h*0.3
            wind = atmo.get_local(self.position.x, self.position.z)[2]
            x = self.position.x + r*np.cos(theta) + wind[0]*0.5
            y = get_terrain_height(self.position.x, self.position.z) + h
            z = self.position.z + r*np.sin(theta) + wind[1]*0.5
            ent.position = (x, y, z)
            ent.color = part['col']
            ent.scale = lerp(0.15, 0.25, h/self.height)
            ent.alpha = lerp(0.8, 0.3, h/self.height)

    def move(self, dx, dz):
        self.position += Vec3(dx, 0, dz)

    def ai_move(self, other_tornado=None):
        # AI Aggressive: direct pursuit of the main tornado
        if other_tornado is not None:
            dx = other_tornado.position.x - self.position.x
            dz = other_tornado.position.z - self.position.z
            norm = np.sqrt(dx*dx + dz*dz)
            speed = 0.35
            if norm > 0.1:
                self.move(speed*dx/norm, speed*dz/norm)
            return
        # Otherwise, Pressure behavior
        px, pz = int(self.position.x//scale), int(self.position.z//scale)
        search_radius = 8
        min_p = atmo.pressure[px, pz]
        target = (px, pz)
        for i in range(max(0, px-search_radius), min(size, px+search_radius)):
            for j in range(max(0, pz-search_radius), min(size, pz+search_radius)):
                if atmo.pressure[i, j] < min_p:
                    min_p = atmo.pressure[i, j]
                    target = (i, j)
        tx, tz = target
        dx = tx*scale - self.position.x
        dz = tz*scale - self.position.z
        norm = np.sqrt(dx*dx + dz*dz)
        speed = 0.25
        if norm > 0.1:
            self.move(speed*dx/norm, speed*dz/norm)

tornadoes = [
    Tornado(pos=(15,0,15), color_base=color.azure, color_top=color.cyan, intensity=1.2, ai_controlled=False),
    Tornado(pos=(30,0,30), color_base=color.orange, color_top=color.red, intensity=1.6, ai_controlled=True)
]

def fuse_tornadoes(t1, t2):
    new_intensity = t1.intensity + t2.intensity
    new_pos = tuple((np.array([t1.position.x, t1.position.y, t1.position.z]) + np.array([t2.position.x, t2.position.y, t2.position.z]))/2)
    if t1 in tornadoes:
        tornadoes.remove(t1)
    if t2 in tornadoes:
        tornadoes.remove(t2)
    for p in t1.particles + t2.particles:
        destroy(p['entity'])
    tornadoes.append(Tornado(
        pos=new_pos,
        color_base=color_lerp(t1.color_base, t2.color_base, 0.5),
        color_top=color_lerp(t1.color_top, t2.color_top, 0.5),
        intensity=new_intensity,
        ai_controlled=True
    ))

mini_grid_step = 2.0
mini_grid_x = np.arange(2, size*scale-2, mini_grid_step)
mini_grid_z = np.arange(2, size*scale-2, mini_grid_step)
mini_arrows = []

mini_map_parent = Entity(parent=camera.ui, enabled=True)
mini_map_bg = Entity(parent=mini_map_parent, model='quad', scale=(0.92,0.92), position=(0.68,0.68,0), color=color.rgba(0,0,0,0.5), eternal=True)

def compute_wind_at_point(point, tornadoes):
    wind = Vec3(0,0,0)
    for t in tornadoes:
        rel = Vec3(point.x - t.position.x, 0, point.z - t.position.z)
        r = rel.length()
        if r < 1e-2:
            continue
        v_theta = t.intensity * 3 / (r+1)
        tangent = Vec3(-rel.z, 0, rel.x).normalized()
        wind += tangent * v_theta
    return wind

def update_minimap():
    for arr in mini_arrows:
        destroy(arr)
    mini_arrows.clear()
    dpx = 0.254
    dpy = 0.225
    for gx in mini_grid_x:
        for gz in mini_grid_z:
            wind = compute_wind_at_point(Vec3(gx,0,gz), tornadoes)
            norm = wind.length()
            if norm < 1e-3:
                wind_dir = Vec3(0,0,1)
            else:
                wind_dir = wind.normalized()

            if norm < 0.5:
                arrow_color = color.green
            elif norm < 1.0:
                arrow_color = color.yellow
            else:
                arrow_color = color.red
            px = (gx/(size*scale)) * 0.28 + dpx
            pz = (gz/(size*scale)) * 0.28 + dpy
            arrow = Entity(parent=mini_map_parent, model='quad', scale=(0.003,0.009), position=(px,pz,-0.01), color=arrow_color)
            angle = np.degrees(np.arctan2(wind_dir.x, wind_dir.z))
            arrow.rotation_z = -angle
            mini_arrows.append(arrow)
            dot = Entity(parent=mini_map_parent, model='circle', scale=0.002, position=(px,pz,-0.01), color=color.green)
            mini_arrows.append(dot)
    for t in tornadoes:
        px = (t.position.x/(size*scale)) * 0.28 + dpx
        pz = (t.position.z/(size*scale)) * 0.28 + dpy
        dot = Entity(parent=mini_map_parent, model='circle', scale=0.018, position=(px,pz,-0.01), color=color.red)
        mini_arrows.append(dot)


def update():
    atmo.update(tornadoes)
    weather.update_weather(tornadoes)

    # Aggressive IA
    if len(tornadoes) > 1:
        player_tornado = tornadoes[0]
        for t in tornadoes[1:]:
            if getattr(t, 'ai_controlled', False):
                t.ai_move(other_tornado=player_tornado)
    elif len(tornadoes) == 1 and getattr(tornadoes[0], 'ai_controlled', False):
        tornadoes[0].ai_move()

    # Collision/merger and immediate stop of the update
    if len(tornadoes) >= 2:
        t1, t2 = tornadoes[0], tornadoes[1]
        dist = np.linalg.norm(np.array([t1.position.x, t1.position.z]) - np.array([t2.position.x, t2.position.z]))
        if dist < 5:
            fuse_tornadoes(t1, t2)
            return

    for t in tornadoes:
        t.update()
    update_minimap()

def input(key):
    if tornadoes and not tornadoes[0].ai_controlled:
        if key == '8':
            tornadoes[0].move(0, 0.5)
        if key == '2':
            tornadoes[0].move(0, -0.5)
        if key == '4' or key == 'a':
            tornadoes[0].move(-0.5, 0)
        if key == '6':
            tornadoes[0].move(0.5, 0)

editor_camera = EditorCamera()
editor_camera.position = Vec3(size*scale//2, 10, -35)

app.run()
