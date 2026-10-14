import math
import sys
import glfw
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from OpenGL.GL import *

# --------------------------------------
# Config / Generalconfig
# --------------------------------------

WIDTH, HEIGHT = 1280, 720
WINDOW_TITLE = "Python 3d Engine [   ]"

GROUND_LEVEL = 1.7
MOVE_SPEED = 5.0
SPRINT = 1.8
JUMP_STRENGTH = 8.0
MULTIPLE_JUMP = 0.8
GRAVITY = -15.0
MOUSE_SENSITIVITY = 0.0022
MAX_JUMPS = 2
PLAYER_RADIUS = 0.3
PLAYER_HEAD = 0.2
LAND_TOLERANCE = 0.05
HUD_LINES = [
    "WASD - MOVE",
    "SHIFT - SPRINT",
    "SPACE - JUMP (2x = DOUBLE JUMP)"
]

# --------------------------------------
# --------------- GUI ------------------
# --------------------------------------

class GUI:
    def create_text_texture(lines, font_size=22, padding=12):
        font = None
        for name in  ("arial.ttf", "DejaVuSans.ttf"):
            try:
                font = ImageFont.truetype(name, font_size)
                break
            except OSError:
                continue
        if font is None:
            font = ImageFont.load_default()

        line_height = font_size + 8
        measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        width = max(int(measure.textlength(line, font=font)) for line in lines) + 2 * padding
        heigth = line_height * len(lines) + 2 * padding
        
        img = Image.new("RGBA", (width, heigth), (0, 0, 0, 140))
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(lines):
            draw.text((padding, padding + i * line_height), line, font=font, fill=(255, 255, 255, 255))
        
        tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, heigth, 0,
                    GL_RGBA, GL_UNSIGNED_BYTE, img.tobytes())
        return tex, width, heigth

    def draw_hud(hud_tex, hud_w, hud_h):
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, WIDTH, HEIGHT, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)

        glBlendFunc(GL_ONE_MINUS_DST_COLOR, GL_ZERO)
        cx, cy = WIDTH / 2, HEIGHT / 2
        size, gap = 12, 4
        glColor3f(1, 1, 1)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        glVertex2f(cx - size, cy); glVertex2f(cx - gap, cy)
        glVertex2f(cx + gap, cy); glVertex2f(cx + size, cy)
        glVertex2f(cx, cy - size); glVertex2f(cx, cy - gap)
        glVertex2f(cx, cy + gap); glVertex2f(cx, cy + size)
        glEnd()
        glLineWidth(1.0)

        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        margin = 15
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, hud_tex)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(margin, margin)
        glTexCoord2f(1, 0); glVertex2f(margin + hud_w, margin)
        glTexCoord2f(1, 1); glVertex2f(margin + hud_w, margin + hud_h)
        glTexCoord2f(0, 1); glVertex2f(margin, margin + hud_h)
        glEnd()
        glDisable(GL_TEXTURE_2D)

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

# --------------------------------------
# gluPerspective / -lookAt substitute
# --------------------------------------

class Matrix:
    def perspective_matrix(fovy_deg, aspect, near, far):
        f = 1.0 / math.tan(math.radians(fovy_deg/2.0))
        m = np.zeros((4,4), dtype=np.float32)
        m[0,0] = f / aspect
        m[1,1] = f
        m[2,2] = (far + near) / (near - far)
        m [2,3] = (2 * far * near) / (near - far)
        m[3,2] = -1.0
        return m.T

    def look_at_matrix(eye, target, up):
        eye = np.array(eye, dtype=np.float32)
        target = np.array(target, dtype=np.float32)
        up = np.array(up, dtype=np.float32)

        f = target - eye
        f = f / np.linalg.norm(f)
        s = np.cross(f, up)
        s = s /np.linalg.norm(s)
        u = np.cross(s, f)

        m = np.identity(4, dtype=np.float32)
        m[0, 0:3] = s
        m[1, 0:3] = u
        m[2 ,0:3] = -f
        m[0, 3] = -np.dot(s, eye)
        m[1, 3] = -np.dot(u, eye)
        m[2, 3] = np.dot(f, eye)
        return m.T

# --------------------------------------
# ------------ Platform ----------------
# --------------------------------------

class Platform:
    def __init__(self, x, y, z, width, height, depth, color=(0.8, 0.45, 0.2)):
        self.min_x, self.max_x = x, x + width
        self.min_y, self.max_y = y, y + height
        self.min_z, self.max_z = z, z + depth
        self.color = color

    def draw(self):
        x0, x1 = self.min_x, self.max_x
        y0, y1 = self.min_y, self.max_y
        z0, z1 = self.min_z, self.max_z
        r, g, b = self.color

        faces = [
            (1.0, [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)]),
            (0.8, [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
            (0.8, [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]),
            (0.6, [(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)]),
            (0.6, [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]), 
        ]

        glBegin(GL_QUADS)
        for shade, verts in faces:
            glColor3f(r*shade, g*shade, b*shade)
            for v in verts:
                glVertex3f(*v)
        glEnd()
# --------------------------------------
# -----------Cam / Player---------------
# --------------------------------------

class Player:
    def __init__(self):
        self.x, self.y, self.z = 0.0, GROUND_LEVEL, 5.0
        self.yaw = 0.0
        self.pitch = 0.0
        self.vel_y = 0.0
        self.on_ground = True
        self.jumps_left = MAX_JUMPS
        self.space_was_pressed = False

        self.first_mouse = True
        self.last_mouse_x = 0.0
        self.last_mouse_y = 0.0

    def process_mouse(self, window):
        xpos, ypos = glfw.get_cursor_pos(window)

        if self.first_mouse:
            self.last_mouse_x, self.last_mouse_y = xpos, ypos
            self.first_mouse = False

        dx = xpos - self.last_mouse_x
        dy = ypos - self.last_mouse_y
        self.last_mouse_x, self.last_mouse_y = xpos, ypos

        self.yaw += dx * MOUSE_SENSITIVITY
        self.pitch -= dy * MOUSE_SENSITIVITY

        max_pitch = math.radians(85.0)
        self.pitch = max(-max_pitch, min(max_pitch, self.pitch))

    def process_input(self, window, dt):
        forward_x, forward_z = math.sin(self.yaw), -math.cos(self.yaw)
        right_x, right_z = math.cos(self.yaw), math.sin(self.yaw)
        currentSpeed = MOVE_SPEED

        move_x = move_z = 0.0
        if glfw.get_key(window, glfw.KEY_W) == glfw.PRESS:
            move_x += forward_x
            move_z += forward_z
        if glfw.get_key(window, glfw.KEY_S) == glfw.PRESS:
            move_x -= forward_x
            move_z -= forward_z
        if glfw.get_key(window, glfw.KEY_D) == glfw.PRESS:
            move_x += right_x
            move_z += right_z
        if glfw.get_key(window, glfw.KEY_A) == glfw.PRESS:
            move_x -= right_x
            move_z -= right_z
        if glfw.get_key(window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS:
            currentSpeed *= SPRINT
            
        length = math.hypot(move_x, move_z)
        if length > 0.0001:
            move_x /= length
            move_z /= length
            self.x += move_x * currentSpeed * dt
            self.z += move_z * currentSpeed * dt

        space_pressed = glfw.get_key(window, glfw.KEY_SPACE) == glfw.PRESS
        if space_pressed and not self.space_was_pressed and self.jumps_left > 0:
            if self.jumps_left == MAX_JUMPS:
                self.vel_y = JUMP_STRENGTH
            else:
                self.vel_y = JUMP_STRENGTH * MULTIPLE_JUMP
            self.on_ground = False
            self.jumps_left -= 1
        self.space_was_pressed = space_pressed

    def collide_platforms_horizontal(self, platforms):
        feet = self.y - GROUND_LEVEL
        head = self.y + PLAYER_HEAD

        for p in platforms:
            if feet >= p.max_y - LAND_TOLERANCE or head <= p.min_y:
                continue

            pen_x_neg = (self.x + PLAYER_RADIUS) - p.min_x
            pen_x_pos = p.max_x - (self.x - PLAYER_RADIUS)
            pen_z_neg = (self.z + PLAYER_RADIUS) - p.min_z
            pen_z_pos = p.max_z - (self.z - PLAYER_RADIUS)

            smallest = min(pen_x_neg, pen_x_pos, pen_z_neg, pen_z_pos)
            if smallest <= 0:
                continue

            if smallest == pen_x_neg:
                self.x -= pen_x_neg
            elif smallest == pen_x_pos:
                self.x += pen_x_pos
            elif smallest == pen_z_neg:
                self.z -= pen_z_neg
            else:
                self.z += pen_z_pos

    def update_physics(self, dt, platforms):
        prev_feet = self.y - GROUND_LEVEL
        self.vel_y += GRAVITY * dt
        self.y += self.vel_y * dt
        feet = self.y - GROUND_LEVEL

        if feet <= 0.0:
            self.y = GROUND_LEVEL
            self.vel_y = 0.0
            self.on_ground = True
            self.jumps_left = MAX_JUMPS

        if self.vel_y <= 0.0:
            for p in platforms:
                over_xz = (p.min_x - PLAYER_RADIUS < self.x < p.max_x + PLAYER_RADIUS and 
                        p.min_z - PLAYER_RADIUS < self.z < p.max_z + PLAYER_RADIUS)
                if over_xz and prev_feet >= p.max_y - LAND_TOLERANCE and feet <= p.max_y:
                    self.y = p.max_y + GROUND_LEVEL
                    self.vel_y = 0.0
                    self.on_ground = True
                    self.jumps_left = MAX_JUMPS

    def apply_view(self):
        forward_x = math.sin(self.yaw) * math.cos(self.pitch)
        forward_y = math.sin(self.pitch)
        forward_z = -math.cos(self.yaw) *math.cos(self.pitch)

        view = Matrix.look_at_matrix(
            eye=(self.x, self.y, self.z),
            target=(self.x + forward_x, self.y + forward_y, self.z + forward_z),
            up = (0.0, 1.0, 0.0),
        )
        glMultMatrixf(view)

# --------------------------------------
# ------------ Rendering ---------------
# --------------------------------------

def draw_grid(size=50, step=1):
    glColor3f(0.35, 0.35, 0.35)
    glBegin(GL_LINES)
    for i in range(-size, size + 1, step):
        glVertex3f(i, 0.0, -size)
        glVertex3f(i, 0.0, size)
        glVertex3f(-size, 0.0, i)
        glVertex3f(size, 0.0, i)
    glEnd()

    glLineWidth(2.0)
    glBegin(GL_LINES)
    glColor3f(1, 0, 0); glVertex3f(0, 0.01, 0); glVertex3f(5, 0.01, 0)
    glColor3f(0, 0, 1); glVertex3f(0, 0.01, 0); glVertex3f(0, 0.01, 5)
    glEnd()
    glLineWidth(1.0)

# --------------------------------------
# OpenGL / Window Setup
# --------------------------------------

def init_gl():
    glClearColor(0.53, 0.81, 0.92, 1.0)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    proj = Matrix.perspective_matrix(70.0, WIDTH / HEIGHT, 0.1, 500.0)
    glMultMatrixf(proj)
    glMatrixMode(GL_MODELVIEW)

def main():
    if not glfw.init():
        print("GLF couldn't be initialised")
        sys.exit(1)

    monitor = glfw.get_primary_monitor()
    mode = glfw.get_video_mode(monitor)

    global WIDTH, HEIGHT
    WIDTH, HEIGHT = mode.size.width, mode.size.height

    window = glfw.create_window(WIDTH, HEIGHT, WINDOW_TITLE, monitor, None)

    if not window:
        glfw.terminate()
        print("Window couldn't be created")
        sys.exit(1)

    glfw.make_context_current(window)
    glfw.swap_interval(1)
    glfw.set_input_mode(window, glfw.CURSOR, glfw.CURSOR_DISABLED)

    init_gl()
    hud_tex, hud_w, hud_h = GUI.create_text_texture(HUD_LINES)
    player = Player()

    platforms = [
        Platform(-2.0, 0.0, -2.0, 4.0, 1.0, 4.0),
        Platform(-2.0, 0.0, -9.0, 4.0, 3.0, 4.0),
        Platform(-8.0, 0.0, -9.0, 4.0, 6.0, 4.0),
        Platform(-8.0, 0.0, -16.0, 10.0, 9.0, 4.0),
        Platform(-20.0, 0.0, -22.0, 4.0, 12.0, 10.0),
        Platform(-20.0, 0.0, -27.0, 1.0, 15.0, 1.0)
    ]

    last_time = glfw.get_time()

    while not glfw.window_should_close(window):
        current_time = glfw.get_time()
        dt = current_time - last_time
        last_time = current_time

        dt = min(dt, 0.05)

        glfw.poll_events()
        if glfw.get_key(window, glfw.KEY_ESCAPE) == glfw.PRESS:
            glfw.set_window_should_close(window, True)

        player.process_mouse(window)
        player.process_input(window, dt)
        player.collide_platforms_horizontal(platforms)
        player.update_physics(dt, platforms)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        player.apply_view()

        draw_grid()
        for p in platforms:
            p.draw()

        GUI.draw_hud(hud_tex, hud_w, hud_h)

        glfw.swap_buffers(window)

    glfw.terminate()

if __name__ == "__main__":
    main()