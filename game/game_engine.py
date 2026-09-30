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
BUTTON_COLOR = (70, 70, 90)
BUTTON_HOVER = (95, 95, 120)
BUTTON_BORDER = (180, 180, 200)

MENU = "MENU"
PLAYING = "PLAYING"
GAME_OVER = "GAME_OVER"


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.marble = Marble(50, 50)

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

        self.difficulty = "Medium"
        self.tilt_strength = 0.6
        self.friction = 0.02
        self.time_limit_ms = 45000
        self.max_speed = 9
        self.restitution = 0.9

        self.walls = self._build_maze()
        self.goal_x, self.goal_y, self.goal_radius = (
            width - 60,
            height - 60,
            22
        )

        self.start_ticks = pygame.time.get_ticks()

        self.font = pygame.font.SysFont("Arial", 26)
        self.title_font = pygame.font.SysFont(
            "Arial",
            48,
            bold=True
        )
        self.small_font = pygame.font.SysFont("Arial", 22)

        self.state = MENU
        self.result = None
        self.finish_time_ms = None

        # Sound setup.
        # Game continues normally if audio initialization fails.
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

    # --------------------------------------------------
    # MAZE
    # --------------------------------------------------

    def _build_maze(self):
        walls = []
        t = 16

        # Outer boundary
        walls.append(Wall(0, 0, self.width, t))
        walls.append(Wall(0, self.height - t, self.width, t))
        walls.append(Wall(0, 0, t, self.height))
        walls.append(Wall(self.width - t, 0, t, self.height))

        # Internal walls
        walls.append(
            Wall(0, 140, self.width - 140, t)
        )
        walls.append(
            Wall(140, 260, self.width - 140, t)
        )
        walls.append(
            Wall(0, 380, self.width - 140, t)
        )

        return walls

    # --------------------------------------------------
    # INPUT / STATE
    # --------------------------------------------------

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:

            if self.state == MENU:
                self._handle_menu_key(event.key)

            elif self.state == GAME_OVER:
                self._handle_game_over_key(event.key)

        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            if self.state == MENU:
                self._select_difficulty(
                    event.pos,
                    menu=True
                )

            elif self.state == GAME_OVER:
                self._select_difficulty(
                    event.pos,
                    menu=False
                )

    def _handle_menu_key(self, key):
        choices = {
            pygame.K_1: "Easy",
            pygame.K_2: "Medium",
            pygame.K_3: "Hard",
        }

        if key in choices:
            self._start_new_round(choices[key])

        elif key in (
            pygame.K_4,
            pygame.K_ESCAPE
        ):
            pygame.event.post(
                pygame.event.Event(pygame.QUIT)
            )

    def _handle_game_over_key(self, key):

        if key == pygame.K_r:
            self._start_new_round(
                self.difficulty
            )

        elif key == pygame.K_1:
            self._start_new_round("Easy")

        elif key == pygame.K_2:
            self._start_new_round("Medium")

        elif key == pygame.K_3:
            self._start_new_round("Hard")

        elif key in (
            pygame.K_4,
            pygame.K_ESCAPE
        ):
            pygame.event.post(
                pygame.event.Event(pygame.QUIT)
            )

        # Any other key is ignored.

    def handle_input(self):
        if self.state != PLAYING:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()

        dx = mouse_x - self.width // 2
        dy = mouse_y - self.height // 2

        dist = max(
            1,
            math.hypot(dx, dy)
        )

        ax = (
            dx / dist
        ) * self.tilt_strength

        ay = (
            dy / dist
        ) * self.tilt_strength

        self.marble.vx += ax
        self.marble.vy += ay

    # --------------------------------------------------
    # GAME UPDATE
    # --------------------------------------------------

    def update(self):
        if self.state != PLAYING:
            return

        elapsed = (
            pygame.time.get_ticks()
            - self.start_ticks
        )

        # Timeout
        if elapsed >= self.time_limit_ms:
            self._finish_round(
                "timeout",
                self.time_limit_ms
            )
            return

        # Friction
        self.marble.vx *= (
            1 - self.friction
        )
        self.marble.vy *= (
            1 - self.friction
        )

        # Speed limit
        speed = math.hypot(
            self.marble.vx,
            self.marble.vy
        )

        if speed > self.max_speed:
            scale = (
                self.max_speed / speed
            )

            self.marble.vx *= scale
            self.marble.vy *= scale

        # Move marble
        self.marble.x += self.marble.vx
        self.marble.y += self.marble.vy

        # Resolve collisions
        self._resolve_wall_collisions()

        # Goal detection
        gx = (
            self.goal_x
            - self.marble.x
        )

        gy = (
            self.goal_y
            - self.marble.y
        )

        if math.hypot(gx, gy) <= self.goal_radius:
            self._finish_round(
                "solved",
                elapsed
            )

    def _finish_round(
        self,
        result,
        finish_time_ms
    ):
        self.state = GAME_OVER
        self.result = result
        self.finish_time_ms = finish_time_ms

        if result == "solved":
            self._play_sound(
                self.goal_sound
            )

        else:
            self._play_sound(
                self.timeout_sound
            )

    # --------------------------------------------------
    # WALL COLLISION
    # --------------------------------------------------

    def _resolve_wall_collisions(self):
        """
        Circle-vs-rectangle collision.

        1. Find closest point on rectangle.
        2. Calculate vector from closest point
           to marble center.
        3. Check penetration.
        4. Normalize collision vector.
        5. Push marble outside wall.
        6. Reflect velocity only when moving
           INTO the wall.
        """

        bounced = False

        for wall in self.walls:

            wall_rect = wall.rect()

            cx = self.marble.x
            cy = self.marble.y
            radius = self.marble.radius

            # Closest point on rectangle
            closest_x = max(
                wall_rect.left,
                min(cx, wall_rect.right)
            )

            closest_y = max(
                wall_rect.top,
                min(cy, wall_rect.bottom)
            )

            # Vector from closest point
            # to marble center
            dx = cx - closest_x
            dy = cy - closest_y

            distance_sq = (
                dx * dx +
                dy * dy
            )

            # No collision
            if distance_sq > radius * radius:
                continue

            # Normal case
            if distance_sq > 1e-12:

                distance = math.sqrt(
                    distance_sq
                )

                nx = dx / distance
                ny = dy / distance

                penetration = (
                    radius - distance
                )

            else:
                # Marble center is inside
                # rectangle or exactly on edge.

                left = (
                    cx - wall_rect.left
                )

                right = (
                    wall_rect.right - cx
                )

                top = (
                    cy - wall_rect.top
                )

                bottom = (
                    wall_rect.bottom - cy
                )

                nearest = min(
                    left,
                    right,
                    top,
                    bottom
                )

                if nearest == left:
                    nx, ny = -1.0, 0.0
                    penetration = radius + left

                elif nearest == right:
                    nx, ny = 1.0, 0.0
                    penetration = radius + right

                elif nearest == top:
                    nx, ny = 0.0, -1.0
                    penetration = radius + top

                else:
                    nx, ny = 0.0, 1.0
                    penetration = radius + bottom

            # Push marble completely outside wall
            self.marble.x += (
                nx * penetration
            )

            self.marble.y += (
                ny * penetration
            )

            # Dot product:
            #
            # < 0 = moving INTO wall
            # > 0 = moving AWAY
            #
            velocity_into_wall = (
                self.marble.vx * nx +
                self.marble.vy * ny
            )

            if velocity_into_wall < 0:

                # Reflect normal component
                # with restitution.
                impulse = (
                    (1.0 + self.restitution)
                    * velocity_into_wall
                )

                self.marble.vx -= (
                    impulse * nx
                )

                self.marble.vy -= (
                    impulse * ny
                )

                bounced = True

        # Only one bounce sound per update.
        if bounced:
            self._play_sound(
                self.bounce_sound
            )

        return bounced

    # --------------------------------------------------
    # RENDERING
    # --------------------------------------------------

    def render(self, screen):

        if self.state == MENU:
            self._render_menu(screen)

        elif self.state == PLAYING:
            self._render_gameplay(screen)

        elif self.state == GAME_OVER:
            self._render_gameplay(screen)
            self._render_game_over(screen)

    def _render_gameplay(self, screen):
        screen.fill(DARK)

        # Walls
        for wall in self.walls:
            pygame.draw.rect(
                screen,
                WALL_COLOR,
                wall.rect()
            )

        # Goal
        pygame.draw.circle(
            screen,
            GOAL_COLOR,
            (
                self.goal_x,
                self.goal_y
            ),
            self.goal_radius
        )

        # Marble
        pygame.draw.circle(
            screen,
            WHITE,
            (
                int(self.marble.x),
                int(self.marble.y)
            ),
            self.marble.radius
        )

        # Timer
        elapsed = (
            pygame.time.get_ticks()
            - self.start_ticks
        )

        seconds_left = max(
            0,
            math.ceil(
                (
                    self.time_limit_ms
                    - elapsed
                ) / 1000
            )
        )

        timer_text = self.font.render(
            f"Time: {seconds_left}s",
            True,
            WHITE
        )

        screen.blit(
            timer_text,
            (10, 10)
        )

        # Difficulty
        difficulty_text = (
            self.small_font.render(
                f"Difficulty: {self.difficulty}",
                True,
                WHITE
            )
        )

        screen.blit(
            difficulty_text,
            (10, 40)
        )

    # --------------------------------------------------
    # START MENU
    # --------------------------------------------------

    def _render_menu(self, screen):
        screen.fill(DARK)

        title = self.title_font.render(
            "MARBLE TILT MAZE",
            True,
            WHITE
        )

        screen.blit(
            title,
            title.get_rect(
                center=(
                    self.width // 2,
                    85
                )
            )
        )

        subtitle = self.font.render(
            "Choose Difficulty",
            True,
            WHITE
        )

        screen.blit(
            subtitle,
            subtitle.get_rect(
                center=(
                    self.width // 2,
                    145
                )
            )
        )

        buttons = self._get_menu_buttons()

        self._draw_buttons(
            screen,
            buttons
        )

    # --------------------------------------------------
    # GAME OVER
    # --------------------------------------------------

    def _render_game_over(self, screen):

        overlay = pygame.Surface(
            (
                self.width,
                self.height
            ),
            pygame.SRCALPHA
        )

        overlay.fill(
            (0, 0, 0, 180)
        )

        screen.blit(
            overlay,
            (0, 0)
        )

        if self.result == "solved":

            title = self.title_font.render(
                "MAZE SOLVED!",
                True,
                GOAL_COLOR
            )

            finish_seconds = (
                self.finish_time_ms / 1000.0
            )

            detail = self.font.render(
                f"Finish time: "
                f"{finish_seconds:.1f}s",
                True,
                WHITE
            )

        else:

            title = self.title_font.render(
                "TIME'S UP!",
                True,
                WHITE
            )

            detail = self.font.render(
                "The maze was not solved.",
                True,
                WHITE
            )

        screen.blit(
            title,
            title.get_rect(
                center=(
                    self.width // 2,
                    90
                )
            )
        )

        screen.blit(
            detail,
            detail.get_rect(
                center=(
                    self.width // 2,
                    145
                )
            )
        )

        controls = self.small_font.render(
            "R = Replay    "
            "1 = Easy    "
            "2 = Medium    "
            "3 = Hard    "
            "4 = Exit",
            True,
            WHITE
        )

        screen.blit(
            controls,
            controls.get_rect(
                center=(
                    self.width // 2,
                    190
                )
            )
        )

        self._draw_buttons(
            screen,
            self._get_game_over_buttons()
        )

    # --------------------------------------------------
    # BUTTONS
    # --------------------------------------------------

    def _draw_buttons(
        self,
        screen,
        buttons
    ):
        mouse_pos = pygame.mouse.get_pos()

        for label, rect in buttons:

            if rect.collidepoint(
                mouse_pos
            ):
                color = BUTTON_HOVER
            else:
                color = BUTTON_COLOR

            pygame.draw.rect(
                screen,
                color,
                rect,
                border_radius=7
            )

            pygame.draw.rect(
                screen,
                BUTTON_BORDER,
                rect,
                width=2,
                border_radius=7
            )

            text = self.font.render(
                label,
                True,
                WHITE
            )

            screen.blit(
                text,
                text.get_rect(
                    center=rect.center
                )
            )

    def _get_menu_buttons(self):
        labels = [
            "Easy",
            "Medium",
            "Hard",
            "Exit"
        ]

        return self._make_button_layout(
            labels,
            center_y=235,
            button_width=130,
            gap=12
        )

    def _get_game_over_buttons(self):
        labels = [
            "Replay",
            "Easy",
            "Medium",
            "Hard",
            "Exit"
        ]

        return self._make_button_layout(
            labels,
            center_y=285,
            button_width=100,
            gap=10
        )

    def _make_button_layout(
        self,
        labels,
        center_y,
        button_width,
        gap
    ):
        button_height = 48

        total_width = (
            len(labels) * button_width
            + (len(labels) - 1) * gap
        )

        start_x = (
            self.width - total_width
        ) // 2

        buttons = []

        for i, label in enumerate(labels):

            rect = pygame.Rect(
                start_x
                + i * (
                    button_width + gap
                ),
                center_y
                - button_height // 2,
                button_width,
                button_height
            )

            buttons.append(
                (label, rect)
            )

        return buttons

    # --------------------------------------------------
    # BUTTON SELECTION
    # --------------------------------------------------

    def _select_difficulty(
        self,
        pos,
        menu=False
    ):
        if menu:
            buttons = (
                self._get_menu_buttons()
            )
        else:
            buttons = (
                self._get_game_over_buttons()
            )

        for label, rect in buttons:

            if rect.collidepoint(pos):

                if label == "Exit":

                    pygame.event.post(
                        pygame.event.Event(
                            pygame.QUIT
                        )
                    )

                elif label == "Replay":

                    self._start_new_round(
                        self.difficulty
                    )

                else:

                    self._start_new_round(
                        label
                    )

                return

    # --------------------------------------------------
    # RESET / NEW ROUND
    # --------------------------------------------------

    def _start_new_round(
        self,
        difficulty
    ):
        settings = (
            self.difficulty_settings[
                difficulty
            ]
        )

        self.difficulty = difficulty

        self.tilt_strength = (
            settings["tilt_strength"]
        )

        self.friction = (
            settings["friction"]
        )

        self.time_limit_ms = (
            settings["time_limit_ms"]
        )

        # Reset marble
        self.marble.x = 50
        self.marble.y = 50

        self.marble.vx = 0
        self.marble.vy = 0

        # Reset game state
        self.result = None
        self.finish_time_ms = None

        # Fresh timer
        self.start_ticks = (
            pygame.time.get_ticks()
        )

        # Start immediately
        self.state = PLAYING

    # --------------------------------------------------
    # SOUND
    # --------------------------------------------------

    def _make_sound(
        self,
        frequency,
        duration
    ):
        sample_rate = 44100

        samples = int(
            sample_rate * duration
        )

        buffer = array.array(
            "h",
            (
                int(
                    32767
                    * 0.25
                    * math.sin(
                        2
                        * math.pi
                        * frequency
                        * i
                        / sample_rate
                    )
                )
                for i in range(samples)
            )
        )

        return pygame.mixer.Sound(
            buffer=buffer.tobytes()
        )

    def _play_sound(self, sound):

        if (
            self.sound_enabled
            and sound is not None
        ):
            sound.play()