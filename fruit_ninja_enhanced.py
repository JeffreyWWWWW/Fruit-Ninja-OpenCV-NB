import pygame
import cv2
import math
import os
import sys
import json
import numpy as np
from hand_tracking import HandTracker
from game_objects import Fruit, BladeTrail
from game_engine import GameEngine
from path_utils import resource_path, data_path

# Initialize Pygame
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
os.environ.setdefault('SDL_VIDEO_CENTERED', '1')
pygame.init()

# Get display info
display_info = pygame.display.Info()
SCREEN_WIDTH = display_info.current_w
SCREEN_HEIGHT = display_info.current_h

# Game constants
WINDOW_WIDTH = 1024
WINDOW_HEIGHT = 768
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600
FPS = 60

# Colors
UI_BLUE = (100, 200, 255)
UI_GOLD = (255, 215, 0)
UI_WHITE = (255, 255, 255)

# Camera preview settings
PREVIEW_SIZE = (320, 240)
PREVIEW_PADDING = 20

class FruitNinja:
    def __init__(self):
        self.is_bundle = hasattr(sys, '_MEIPASS')
        if not self.is_bundle:
            for dir_name in ['fruits', 'cursor', 'sounds', 'fonts', 'background', 'music', 'assets']:
                os.makedirs(resource_path(dir_name), exist_ok=True)
        
        # Initialize display
        self.is_fullscreen = False
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("水果忍者：终极增强版")
        self.clock = pygame.time.Clock()
        self.windowed_size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # Calculate scaling factors for different resolutions
        self.update_screen_scaling()
        
        # Initialize game components
        self.engine = GameEngine(self.screen_width, self.screen_height)
        self.hand_tracker = HandTracker()
        self.blade_trail = None
        self.fruits = []
        self.reset_game_entities()
        
        # Initialize camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Create static surfaces
        self.preview_bg = pygame.Surface((PREVIEW_SIZE[0] + 4, PREVIEW_SIZE[1] + 4))
        self.preview_bg.fill(UI_WHITE)
        
        # UI Elements
        font_candidates = [resource_path('fonts', '华文新魏.ttf'), resource_path('fonts', 'ninja.ttf')]
        self.primary_font_path = next((path for path in font_candidates if os.path.exists(path)), None)
        try:
            if self.primary_font_path:
                self.font = pygame.font.Font(self.primary_font_path, 36)
                self.small_font = pygame.font.Font(self.primary_font_path, 24)
                self.title_font = pygame.font.Font(self.primary_font_path, 64)
            else:
                raise FileNotFoundError
        except:
            self.font = pygame.font.Font(None, 36)
            self.small_font = pygame.font.Font(None, 24)
            self.title_font = pygame.font.Font(None, 64)
        
        # Special font for menu/leaderboard
        menu_font_path = resource_path('fonts', '华文新魏.ttf')
        if not os.path.exists(menu_font_path):
            menu_font_path = self.primary_font_path
        try:
            if menu_font_path:
                self.menu_font = pygame.font.Font(menu_font_path, 36)
                self.menu_small_font = pygame.font.Font(menu_font_path, 24)
                self.menu_title_font = pygame.font.Font(menu_font_path, 72)
            else:
                raise FileNotFoundError
        except:
            fallback = pygame.font.Font(None, 36)
            self.menu_font = fallback
            self.menu_small_font = pygame.font.Font(None, 24)
            self.menu_title_font = pygame.font.Font(None, 72)

        # Menu / leaderboard state
        self.state = 'menu'
        self.player_name_input = ''
        self.player_name = ''
        self.name_error = ''
        self.final_score = 0
        self.session_active = False
        self.leaderboard_file = data_path('leaderboard.json')
        self.leaderboard = self.load_leaderboard()
        self.last_submission = None
        self.round_duration = 60 * 1000  # 1 minute rounds
        self.round_end_time = None
        
        # Music configuration
        self.menu_music_path = resource_path('music', 'menu_theme.mp3')
        self.gameplay_music_path = resource_path('music', 'gameplay_theme.mp3')
        self.music_volumes = {'menu': 0.45, 'gameplay': 0.35}
        self.current_music = None
        self.music_enabled = pygame.mixer.get_init() is not None
        self.play_menu_music()
    
    def update_screen_scaling(self):
        self.screen_width, self.screen_height = self.screen.get_size()
        self.scale_x = self.screen_width / WINDOW_WIDTH
        self.scale_y = self.screen_height / WINDOW_HEIGHT
    
    def on_window_size_change(self):
        self.update_screen_scaling()
        self.engine.resize(self.screen_width, self.screen_height)
        if self.blade_trail:
            self.blade_trail.update_window_size(self.screen_width, self.screen_height)
        for fruit in self.fruits:
            fruit.update_window_size(self.screen_width, self.screen_height)
    
    def handle_window_resize(self, width, height):
        if self.is_fullscreen:
            return
        width = max(MIN_WINDOW_WIDTH, width)
        height = max(MIN_WINDOW_HEIGHT, height)
        self.windowed_size = (width, height)
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        self.on_window_size_change()
    
    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.windowed_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.on_window_size_change()
    
    def reset_game_entities(self):
        self.blade_trail = BladeTrail(self.screen_width, self.screen_height)
        self.fruits = [Fruit(self.screen_width, self.screen_height) for _ in range(5)]
    
    def start_game_session(self):
        self.reset_game_entities()
        self.engine.reset_state()
        self.session_active = True
        self.final_score = 0
        self.round_end_time = pygame.time.get_ticks() + self.round_duration
        self.state = 'playing'
        self.play_gameplay_music()
    
    def end_game_session(self, show_leaderboard=True):
        if not self.session_active:
            return
        self.final_score = self.engine.score
        self.round_end_time = None
        if self.player_name:
            self.add_score_to_leaderboard(self.player_name, self.final_score)
        self.session_active = False
        if show_leaderboard:
            self.play_menu_music()
            self.state = 'leaderboard'
        else:
            self.stop_music()
    
    def load_leaderboard(self):
        if os.path.exists(self.leaderboard_file):
            try:
                with open(self.leaderboard_file, 'r', encoding='utf-8') as leaderboard_file:
                    data = json.load(leaderboard_file)
                    if isinstance(data, list):
                        return sorted(
                            (entry for entry in data if 'name' in entry and 'score' in entry),
                            key=lambda item: item['score'],
                            reverse=True
                        )[:10]
            except Exception as e:
                print(f"Error reading leaderboard: {e}")
        return []
    
    def save_leaderboard(self):
        try:
            with open(self.leaderboard_file, 'w', encoding='utf-8') as leaderboard_file:
                json.dump(self.leaderboard, leaderboard_file, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving leaderboard: {e}")
    
    def add_score_to_leaderboard(self, name, score):
        entry = {'name': name, 'score': score}
        self.leaderboard.append(entry)
        self.leaderboard = sorted(self.leaderboard, key=lambda item: item['score'], reverse=True)[:10]
        self.last_submission = entry
        self.save_leaderboard()
    
    def scale_position(self, x, y):
        # Scale position from camera space (0-1) to screen space with proper range
        # Add offset to center the movement range
        x = (x - 0.1) * 1.25  # Expand range by 25% and offset by 0.1
        y = (y - 0.1) * 1.25
        
        # Clamp values to 0-1 range
        x = max(0, min(1, x))
        y = max(0, min(1, y))
        
        # Scale to screen coordinates
        return int(x * self.screen_width), int(y * self.screen_height)
    
    def frame_to_surface(self, frame):
        try:
            # Resize frame for preview
            frame = cv2.resize(frame, PREVIEW_SIZE)
            # Convert from BGR to RGB and rotate correctly
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Create pygame surface
            surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
            return surface
        except Exception as e:
            print(f"Error converting frame: {e}")
            # Return black surface if conversion fails
            surface = pygame.Surface(PREVIEW_SIZE)
            surface.fill((0, 0, 0))
            return surface
    
    def draw_camera_preview(self, frame, hand_pos, velocity):
        try:
            # Draw tracking visualization
            preview_frame = self.hand_tracker.draw_tracking_info(frame.copy(), hand_pos, velocity)
            
            # Convert frame to pygame surface
            preview_surface = self.frame_to_surface(preview_frame)
            
            # Calculate preview position (bottom-right corner)
            preview_x = self.screen_width - PREVIEW_SIZE[0] - PREVIEW_PADDING
            preview_y = self.screen_height - PREVIEW_SIZE[1] - PREVIEW_PADDING
            
            # Draw background for preview
            self.screen.blit(self.preview_bg, (preview_x - 2, preview_y - 2))
            
            # Draw preview
            self.screen.blit(preview_surface, (preview_x, preview_y))
            
            # Draw connection line between hand and cursor if hand is detected
            if hand_pos[0] is not None and hand_pos[1] is not None:
                game_x, game_y = self.scale_position(hand_pos[0], hand_pos[1])
                preview_hand_x = preview_x + int(hand_pos[0] * PREVIEW_SIZE[0])
                preview_hand_y = preview_y + int(hand_pos[1] * PREVIEW_SIZE[1])
                
                # Draw connecting line with fade effect
                for i in range(3):
                    alpha = 150 - i * 40
                    color = (*UI_BLUE[:3], alpha)
                    line_surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
                    pygame.draw.line(line_surface, color, 
                                  (preview_hand_x, preview_hand_y),
                                  (game_x, game_y), 2)
                    self.screen.blit(line_surface, (0, 0))
        
        except Exception as e:
            print(f"Error drawing preview: {e}")
    
    def update_fruits(self):
        active_fruits = sum(1 for fruit in self.fruits if not fruit.sliced)
        if active_fruits < 3:
            self.fruits.append(Fruit(self.screen_width, self.screen_height))
            if len(self.fruits) > 8:
                self.fruits.pop(0)
    
    def check_collisions(self, blade_points):
        if len(blade_points) < 2:
            return
        
        # Get latest blade movement
        p1 = blade_points[-2]
        p2 = blade_points[-1]
        
        # Calculate blade velocity and angle
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        blade_velocity = math.sqrt(dx*dx + dy*dy)
        slice_angle = math.degrees(math.atan2(dy, dx))
        
        if blade_velocity < 15:  # Minimum velocity for valid slice
            return
        
        # Check collision with each fruit
        for fruit in self.fruits:
            if not fruit.sliced:
                # Calculate distance from fruit to blade line segment
                fruit_radius = 35 * min(self.scale_x, self.scale_y)  # Scale hitbox with screen size
                dist = abs(dy*fruit.x - dx*fruit.y + p2[0]*p1[1] - p2[1]*p1[0]) / blade_velocity
                
                if dist < fruit_radius:
                    fruit.sliced = True
                    current_time = pygame.time.get_ticks()
                    fruit.slice_time = current_time
                    fruit.slice_direction = slice_angle
                    
                    if getattr(fruit, 'is_bomb', False):
                        # Trigger visual and audio feedback for the bomb hit
                        fruit.trigger_bomb_explosion()
                        self.engine.play_explosion_sound()
                        self.engine.apply_bomb_penalty()
                    else:
                        # Standard fruit slice reward path
                        fruit.create_particles(slice_angle)
                        self.engine.play_slice_sound()
                        self.engine.score += 10 * (self.engine.combo + 1)
                        self.engine.update_combo(current_time)
    
    def draw_ui(self):
        # Draw score with glow effect
        score_text = f'得分：{self.engine.score}'
        
        # Glow effect
        glow_size = int(36 * self.scale_y + math.sin(pygame.time.get_ticks() * 0.005) * 2)
        if self.primary_font_path and os.path.exists(self.primary_font_path):
            glow_font = pygame.font.Font(self.primary_font_path, glow_size)
        else:
            glow_font = pygame.font.Font(None, glow_size)
        glow_surface = glow_font.render(score_text, True, UI_BLUE)
        glow_rect = glow_surface.get_rect(topleft=(20 * self.scale_x, 20 * self.scale_y))
        
        # Apply glow
        for offset in [(2, 2), (-2, -2), (2, -2), (-2, 2)]:
            self.screen.blit(glow_surface, (glow_rect.x + offset[0], glow_rect.y + offset[1]))
        
        # Main score text
        score_surface = self.font.render(score_text, True, UI_WHITE)
        self.screen.blit(score_surface, (20 * self.scale_x, 20 * self.scale_y))
        
        # Draw combo with animation
        if self.engine.combo > 1:
            combo_text = f'连击 x{self.engine.combo}!'
            scale = 1.0 + math.sin(pygame.time.get_ticks() * 0.01) * 0.1
            combo_surface = self.small_font.render(combo_text, True, UI_GOLD)
            scaled_surface = pygame.transform.scale(combo_surface, 
                (int(combo_surface.get_width() * scale * self.scale_x),
                 int(combo_surface.get_height() * scale * self.scale_y)))
            combo_pos = (self.screen_width // 2 - scaled_surface.get_width() // 2, 
                        50 * self.scale_y)
            self.screen.blit(scaled_surface, combo_pos)
        
        if self.player_name:
            player_surface = self.small_font.render(f'玩家：{self.player_name}', True, UI_WHITE)
            self.screen.blit(player_surface, (20 * self.scale_x, 60 * self.scale_y))
            hint_surface = self.small_font.render('每个水果基础得分 10 分', True, UI_WHITE)
            hint_y = 60 * self.scale_y + player_surface.get_height() + 5
            self.screen.blit(hint_surface, (20 * self.scale_x, hint_y))
        
        if self.state == 'playing' and self.round_end_time:
            remaining = max(0, self.round_end_time - pygame.time.get_ticks())
            seconds_left = remaining // 1000
            minutes = seconds_left // 60
            seconds = seconds_left % 60
            timer_text = f'{minutes:01}:{seconds:02}'
            timer_surface = self.font.render(timer_text, True, UI_WHITE)
            timer_rect = timer_surface.get_rect(topright=(self.screen_width - 20 * self.scale_x, 20 * self.scale_y))
            self.screen.blit(timer_surface, timer_rect)
    
    def play_music_track(self, path, track_key):
        if not self.music_enabled or not path or not os.path.exists(path):
            return
        if self.current_music == path and pygame.mixer.music.get_busy():
            target_volume = self.music_volumes.get(track_key, 0.4)
            pygame.mixer.music.set_volume(target_volume)
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volumes.get(track_key, 0.4))
            pygame.mixer.music.play(-1)
            self.current_music = path
        except Exception as e:
            print(f"Error playing music {path}: {e}")
    
    def play_menu_music(self):
        self.play_music_track(self.menu_music_path, 'menu')
    
    def play_gameplay_music(self):
        self.play_music_track(self.gameplay_music_path, 'gameplay')
    
    def stop_music(self):
        if self.music_enabled:
            pygame.mixer.music.stop()
        self.current_music = None
    
    def wrap_text(self, text, font, max_width):
        if max_width <= 0:
            return [text]
        lines = []
        current_line = ''
        for char in text:
            if char == '\n':
                lines.append(current_line)
                current_line = ''
                continue
            candidate = f"{current_line}{char}"
            if not current_line or font.size(candidate)[0] <= max_width:
                current_line = candidate
            else:
                lines.append(current_line)
                current_line = char
        if current_line:
            lines.append(current_line)
        return lines
    
    def draw_text_block(self, text, font, color, start_pos, max_width, line_spacing=6):
        x, y = start_pos
        for line in self.wrap_text(text, font, max_width):
            surface = font.render(line, True, color)
            self.screen.blit(surface, (x, y))
            y += surface.get_height() + line_spacing
        return y

    def draw_menu(self):
        self.engine.draw_background(self.screen)
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        title_surface = self.menu_title_font.render("水果忍者", True, UI_WHITE)
        title_rect = title_surface.get_rect(center=(self.screen_width // 2, int(120 * self.scale_y)))
        self.screen.blit(title_surface, title_rect)
        
        content_width = min(int(self.screen_width * 0.8), 900)
        content_x = self.screen_width // 2 - content_width // 2
        prompt_y = title_rect.bottom + 30
        prompt_y = self.draw_text_block(
            "输入姓名后按 Enter 开始游戏",
            self.menu_small_font,
            UI_WHITE,
            (content_x, prompt_y),
            content_width
        )
        
        input_width = min(460, content_width - 80)
        input_height = 58
        input_rect = pygame.Rect(
            content_x,
            prompt_y + 10,
            input_width,
            input_height
        )
        pygame.draw.rect(self.screen, UI_WHITE, input_rect, width=3, border_radius=10)
        cursor_visible = (pygame.time.get_ticks() // 400) % 2 == 0
        if self.player_name_input:
            name_display = self.player_name_input + ("_" if cursor_visible else "")
            color = UI_WHITE
        else:
            name_display = "请输入姓名"
            color = (180, 180, 180)
        input_surface = self.menu_font.render(name_display, True, color)
        self.screen.blit(input_surface, (input_rect.x + 15, input_rect.y + 10))
        
        if self.name_error:
            error_surface = self.menu_small_font.render(self.name_error, True, (255, 100, 100))
            self.screen.blit(error_surface, (input_rect.x, input_rect.bottom + 8))
        
        rules = [
            "玩法说明：",
            "1. 每切中一颗水果基础得分 10 分并可累积连击。",
            "2. 切到炸弹会扣 40 分并清空连击。",
            "3. 按 ESC 结束本局并查看榜单。",
            "4. 每局时长为 60 秒。",
            "5. 按 F11 可切换全屏 / 窗口模式。"
        ]
        rules_y = input_rect.bottom + 40
        for idx, line in enumerate(rules):
            color = UI_GOLD if idx == 0 else UI_WHITE
            rules_y = self.draw_text_block(
                line,
                self.menu_small_font,
                color,
                (input_rect.x, rules_y),
                content_width
            ) + 6
        
        leaderboard_title = self.menu_small_font.render("前十排行榜", True, UI_GOLD)
        leaderboard_x = input_rect.x
        leaderboard_y = rules_y + 20
        self.screen.blit(leaderboard_title, (leaderboard_x, leaderboard_y))
        
        entries = self.leaderboard[:10]
        if entries:
            column_count = 2
            column_spacing = 40
            column_width = (content_width - column_spacing) // column_count
            rows_per_column = math.ceil(len(entries) / column_count)
            row_height = self.menu_small_font.get_height() + 6
            start_y = leaderboard_y + 30
            
            for idx, entry in enumerate(entries, start=1):
                column = (idx - 1) // rows_per_column
                row = (idx - 1) % rows_per_column
                column_x = leaderboard_x + column * (column_width + column_spacing)
                entry_y = start_y + row * row_height
                entry_name = entry.get('name', '???')
                entry_score = entry.get('score', 0)
                text = f"{idx}. {entry_name}：{entry_score}"
                self.draw_text_block(
                    text,
                    self.menu_small_font,
                    UI_WHITE,
                    (column_x, entry_y),
                    column_width
                )
    
    def draw_leaderboard_screen(self):
        self.engine.draw_background(self.screen)
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))
        
        title_surface = self.menu_title_font.render("排行榜", True, UI_GOLD)
        title_rect = title_surface.get_rect(center=(self.screen_width // 2, int(110 * self.scale_y)))
        self.screen.blit(title_surface, title_rect)
        
        summary_text = f"{self.player_name or '玩家'} 本局得分：{self.final_score}"
        summary_surface = self.menu_font.render(summary_text, True, UI_WHITE)
        summary_rect = summary_surface.get_rect(center=(self.screen_width // 2, title_rect.bottom + 40))
        self.screen.blit(summary_surface, summary_rect)
        
        leaderboard_y = summary_rect.bottom + 30
        for idx, entry in enumerate(self.leaderboard[:10], start=1):
            entry_name = entry.get('name', '???')
            entry_score = entry.get('score', 0)
            is_last = entry is self.last_submission
            color = UI_GOLD if is_last else UI_WHITE
            line_surface = self.menu_small_font.render(f"{idx}. {entry_name}：{entry_score}", True, color)
            line_rect = line_surface.get_rect(center=(self.screen_width // 2, leaderboard_y + idx * 32))
            self.screen.blit(line_surface, line_rect)
        
        instructions = [
            "Enter：返回开始界面重新输入姓名",
            "ESC：退出游戏",
            "F11：切换全屏 / 窗口模式"
        ]
        footer_y = self.screen_height - 120
        for i, line in enumerate(instructions):
            instruction_surface = self.menu_small_font.render(line, True, UI_WHITE)
            instruction_rect = instruction_surface.get_rect(center=(self.screen_width // 2, footer_y + i * 28))
            self.screen.blit(instruction_surface, instruction_rect)
    
    def menu_frame(self):
        self.play_menu_music()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.VIDEORESIZE:
                self.handle_window_resize(event.w, event.h)
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                    continue
                elif event.key == pygame.K_BACKSPACE:
                    self.player_name_input = self.player_name_input[:-1]
                    self.name_error = ''
                elif event.key == pygame.K_RETURN:
                    name = self.player_name_input.strip()
                    if name:
                        self.player_name = name
                        self.player_name_input = ''
                        self.name_error = ''
                        self.start_game_session()
                        return True
                    else:
                        self.name_error = "请输入姓名后再开始游戏"
                else:
                    if (len(self.player_name_input) < 12 and event.unicode 
                            and event.unicode.isprintable() and event.unicode not in '\r\n\t'):
                        self.player_name_input += event.unicode
                        self.name_error = ''
        self.draw_menu()
        pygame.display.flip()
        self.clock.tick(FPS)
        return True
    
    def leaderboard_frame(self):
        self.play_menu_music()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.VIDEORESIZE:
                self.handle_window_resize(event.w, event.h)
                continue
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                    continue
                if event.key == pygame.K_RETURN:
                    self.player_name_input = ''
                    self.player_name = ''
                    self.name_error = ''
                    self.last_submission = None
                    self.state = 'menu'
                    return True
        self.draw_leaderboard_screen()
        pygame.display.flip()
        self.clock.tick(FPS)
        return True
    
    def run(self):
        running = True
        while running:
            if self.state == 'menu':
                running = self.menu_frame()
                continue
            if self.state == 'leaderboard':
                running = self.leaderboard_frame()
                continue
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.end_game_session(show_leaderboard=False)
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_window_resize(event.w, event.h)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.is_fullscreen:
                            self.toggle_fullscreen()
                        else:
                            self.end_game_session()
                    elif event.key == pygame.K_F11:
                        self.toggle_fullscreen()
            if not running:
                break
            if self.state != 'playing':
                continue
            if self.round_end_time and pygame.time.get_ticks() >= self.round_end_time:
                self.end_game_session()
                continue
            
            # Draw background
            self.engine.draw_background(self.screen)
            
            # Process hand tracking
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                hand_x, hand_y, velocity, vel_vector = self.hand_tracker.get_hand_position(frame)
                
                if hand_x is not None:
                    # Scale position to screen coordinates
                    game_x, game_y = self.scale_position(hand_x, hand_y)
                    point = (game_x, game_y)
                    
                    # Update and draw blade trail
                    self.blade_trail.add_point(point, velocity)
                    self.blade_trail.draw(self.screen)
                    
                    # Draw katana cursor
                    if len(self.blade_trail.points) > 1:
                        p1 = self.blade_trail.points[-2]
                        p2 = self.blade_trail.points[-1]
                        angle = math.degrees(math.atan2(-(p2[1] - p1[1]), p2[0] - p1[0]))
                        self.engine.draw_katana(self.screen, point, angle)
                    
                    # Check collisions
                    self.check_collisions(self.blade_trail.points)
                
                # Draw camera preview with tracking visualization
                self.draw_camera_preview(frame, (hand_x, hand_y), vel_vector)
            
            # Update and draw fruits
            self.update_fruits()
            for fruit in self.fruits:
                fruit.update()
                fruit.draw(self.screen)
            
            # Draw UI
            self.draw_ui()
            
            # Update display
            pygame.display.flip()
            self.clock.tick(FPS)
        
        # Cleanup
        self.stop_music()
        self.cap.release()
        pygame.quit()

if __name__ == "__main__":
    game = FruitNinja()
    game.run()