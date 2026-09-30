import pygame
from .marble import Marble
from .wall import Wall
import math
import array

# Game Engine

WHITE = (255, 255, 255)
DARK = (40, 40, 50)
WALL_COLOR = (90, 90, 110)
GOAL_COLOR = (60, 200, 120)

class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.marble = Marble(50, 50)
        # Default = Medium
        self.difficulty = "Medium"
        self.tilt_strength = 0.6
        self.friction = 0.02
        self.max_speed = 9

        self.difficulty_settings = {
            "Easy": {
                "tilt_strength": 0.4,
                "friction": 0.04,
                "time_limit_ms": 60000
            },
            "Medium": {
                "tilt_strength": 0.6,
                "friction": 0.02,
                "time_limit_ms": 45000
            },
            "Hard": {
                "tilt_strength": 0.8,
                "friction": 0.01,
                "time_limit_ms": 30000
            }
        }

        self.walls = self._build_maze()
        self.goal_x, self.goal_y, self.goal_radius = width - 60, height - 60, 22

        self.time_limit_ms = 45000
        self.start_ticks = pygame.time.get_ticks()

        self.font = pygame.font.SysFont("Arial", 26)
        self.title_font = pygame.font.SysFont("Arial", 48, bold=True)
        self.game_over = False
        self.result = None
        self.finish_time_ms = None

        # Sound setup. The game still works if audio is unavailable.
        self.sound_enabled = False
        self.bounce_sound = None
        self.goal_sound = None
        self.timeout_sound = None

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()

            self.bounce_sound = self._make_sound(180, 0.08)
            self.goal_sound = self._make_sound(700, 0.20)
            self.timeout_sound = self._make_sound(100, 0.30)
            self.sound_enabled = True
        except pygame.error:
            pass

    def _build_maze(self):
        walls = []
        t = 16  # wall thickness

        # outer boundary
        walls.append(Wall(0, 0, self.width, t))
        walls.append(Wall(0, self.height - t, self.width, t))
        walls.append(Wall(0, 0, t, self.height))
        walls.append(Wall(self.width - t, 0, t, self.height))

        # a few internal walls forming a simple winding path
        walls.append(Wall(0, 140, self.width - 140, t))
        walls.append(Wall(140, 260, self.width - 140, t))
        walls.append(Wall(0, 380, self.width - 140, t))

        return walls

    def handle_event(self, event):
        if not self.game_over:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                self._start_new_round("Easy")

            elif event.key == pygame.K_2:
                self._start_new_round("Medium")

            elif event.key == pygame.K_3:
                self._start_new_round("Hard")

            elif event.key in (pygame.K_4, pygame.K_ESCAPE):
                pygame.event.post(pygame.event.Event(pygame.QUIT))

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self._select_difficulty(event.pos)

    def handle_input(self):
        if self.game_over:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - self.width // 2
        dy = mouse_y - self.height // 2
        dist = max(1, (dx ** 2 + dy ** 2) ** 0.5)
        ax = (dx / dist) * self.tilt_strength
        ay = (dy / dist) * self.tilt_strength
        self.marble.vx += ax
        self.marble.vy += ay

    def update(self):
        if self.game_over:
            return

        elapsed = pygame.time.get_ticks() - self.start_ticks
        if elapsed >= self.time_limit_ms:
            self.game_over = True
            self.result = "timeout"
            self.finish_time_ms = self.time_limit_ms
            self._play_sound(self.timeout_sound)
            return

        self.marble.vx *= (1 - self.friction)
        self.marble.vy *= (1 - self.friction)

        speed = (self.marble.vx ** 2 + self.marble.vy ** 2) ** 0.5
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.marble.vx *= scale
            self.marble.vy *= scale

        self.marble.x += self.marble.vx
        self.marble.y += self.marble.vy

        self._resolve_wall_collisions()

        gx = self.goal_x - self.marble.x
        gy = self.goal_y - self.marble.y
        if (gx ** 2 + gy ** 2) ** 0.5 <= self.goal_radius:
            self.game_over = True
            self.result = "solved"
            self.finish_time_ms = elapsed
            self._play_sound(self.goal_sound)

    def _resolve_wall_collisions(self):
        for wall in self.walls:
            wall_rect = wall.rect()
            cx, cy = self.marble.x, self.marble.y
            radius = self.marble.radius

            # Find the closest point on the wall rectangle to the marble center.
            closest_x = max(wall_rect.left, min(cx, wall_rect.right))
            closest_y = max(wall_rect.top, min(cy, wall_rect.bottom))

            dx = cx - closest_x
            dy = cy - closest_y
            distance_sq = dx * dx + dy * dy

            # True circle-vs-rectangle collision.
            if distance_sq <= radius * radius:
                if distance_sq > 0:
                    distance = distance_sq ** 0.5
                    nx = dx / distance
                    ny = dy / distance
                    penetration = radius - distance

                else:
                    # Marble center is inside the wall.
                    # Push it out through the nearest wall face.
                    left = cx - wall_rect.left
                    right = wall_rect.right - cx
                    top = cy - wall_rect.top
                    bottom = wall_rect.bottom - cy

                    nearest = min(left, right, top, bottom)

                    if nearest == left:
                        nx, ny = -1, 0
                        penetration = radius + left
                    elif nearest == right:
                        nx, ny = 1, 0
                        penetration = radius + right
                    elif nearest == top:
                        nx, ny = 0, -1
                        penetration = radius + top
                    else:
                        nx, ny = 0, 1
                        penetration = radius + bottom

                # Move the marble completely outside the wall.
                self.marble.x += nx * penetration
                self.marble.y += ny * penetration

                # Preserve the existing bounce behavior while only
                # reflecting the velocity component going into the wall.
                velocity_into_wall = (
                    self.marble.vx * nx + self.marble.vy * ny
                )

                if velocity_into_wall < 0:
                    self.marble.vx -= 1.3 * velocity_into_wall * nx
                    self.marble.vy -= 1.3 * velocity_into_wall * ny
                    self._play_sound(self.bounce_sound)

    def render(self, screen):
        screen.fill(DARK)

        for wall in self.walls:
            pygame.draw.rect(screen, WALL_COLOR, wall.rect())

        pygame.draw.circle(
            screen,
            GOAL_COLOR,
            (self.goal_x, self.goal_y),
            self.goal_radius
        )
        pygame.draw.circle(
            screen,
            WHITE,
            (int(self.marble.x), int(self.marble.y)),
            self.marble.radius
        )

        # Keep the normal timer visible during gameplay.
        elapsed = pygame.time.get_ticks() - self.start_ticks
        seconds_left = max(0, (self.time_limit_ms - elapsed) // 1000)

        timer_text = self.font.render(
            f"Time: {seconds_left}s",
            True,
            WHITE
        )
        screen.blit(timer_text, (10, 10))

        # Graphical game-over screen.
        if self.game_over:
            # Dark transparent overlay.
            overlay = pygame.Surface((self.width, self.height))
            overlay.set_alpha(180)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))

            if self.result == "solved":
                title = pygame.font.SysFont("Arial", 48, bold=True).render(
                    "MAZE SOLVED!",
                    True,
                    GOAL_COLOR
                )

                finish_seconds = self.finish_time_ms / 1000.0
                time_text = self.font.render(
                    f"Finish time: {finish_seconds:.1f}s",
                    True,
                    WHITE
                )
            else:
                title = pygame.font.SysFont("Arial", 48, bold=True).render(
                    "TIME'S UP!",
                    True,
                    WHITE
                )

                time_text = self.font.render(
                    "The maze was not solved.",
                    True,
                    WHITE
                )

            wait_text = self.font.render(
                "Press any key or close the window to exit.",
                True,
                WHITE
            )

            screen.blit(
                title,
                title.get_rect(center=(self.width // 2, self.height // 2 - 60))
            )

            screen.blit(
                time_text,
                time_text.get_rect(center=(self.width // 2, self.height // 2))
            )

            screen.blit(
                wait_text,
                wait_text.get_rect(center=(self.width // 2, self.height // 2 + 50))
            )
    def _make_sound(self, frequency, duration):
        sample_rate = 44100
        samples = int(sample_rate * duration)

        buffer = array.array(
            "h",
            (
                int(
                    32767
                    * 0.25
                    * math.sin(2 * math.pi * frequency * i / sample_rate)
                )
                for i in range(samples)
            )
        )

        return pygame.mixer.Sound(buffer=buffer.tobytes())


    def _play_sound(self, sound):
        if self.sound_enabled and sound is not None:
            sound.play()


    def _start_new_round(self, difficulty):
        settings = self.difficulty_settings[difficulty]

        self.difficulty = difficulty
        self.tilt_strength = settings["tilt_strength"]
        self.friction = settings["friction"]
        self.time_limit_ms = settings["time_limit_ms"]

        # Reset marble.
        self.marble.x = 50
        self.marble.y = 50
        self.marble.vx = 0
        self.marble.vy = 0

        # Reset round state.
        self.start_ticks = pygame.time.get_ticks()
        self.game_over = False
        self.result = None
        self.finish_time_ms = None
        self._game_over_logged = False


    def _select_difficulty(self, pos):
        x, y = pos

        # Difficulty buttons are centered around the bottom half
        # of the game-over screen.
        button_width = 170
        button_height = 45
        gap = 15

        start_x = (
            self.width
            - (button_width * 4 + gap * 3)
        ) // 2

        if not (
            self.height // 2 + 80
            <= y
            <= self.height // 2 + 80 + button_height
        ):
            return

        choices = ["Easy", "Medium", "Hard", "Exit"]

        for i, choice in enumerate(choices):
            left = start_x + i * (button_width + gap)

            if left <= x <= left + button_width:
                if choice == "Exit":
                    pygame.event.post(pygame.event.Event(pygame.QUIT))
                else:
                    self._start_new_round(choice)

                return
