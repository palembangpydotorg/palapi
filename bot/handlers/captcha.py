import os
import random
import numpy as np
from manim import *

class ClockCaptchaScene(Scene):
    def construct(self):
        target_number = random.randint(1, 9)
        
        with open("/tmp/captcha_ans.txt", "w") as f:
            f.write(str(target_number))

        title = Text("PalembangPy Security", font_size=20, color=BLUE).to_edge(UP, buff=0.2)
        subtitle = Text("Pilih angka yang ditunjuk jarum!", font_size=16, color=YELLOW).next_to(title, DOWN, buff=0.1)

        circle = Circle(radius=1.6, color=WHITE, stroke_width=2).shift(DOWN * 0.3)
        center_dot = Dot(color=WHITE).shift(DOWN * 0.3)
        
        num_list = list(range(1, 10))
        random.shuffle(num_list)
        
        number_objects = {}
        for i, num in enumerate(num_list):
            angle = i * (2 * PI / len(num_list)) - PI / 2
            x = 1.1 * np.cos(angle)
            y = 1.1 * np.sin(angle) + 0.3
            
            num_mobject = Text(str(num), font_size=28, color=WHITE)
            num_mobject.move_to(np.array([x, -y, 0]))
            number_objects[num] = num_mobject

        target_index = num_list.index(target_number)
        target_angle = target_index * (2 * PI / len(num_list)) - PI / 2
        
        hand_end_x = 0.9 * np.cos(target_angle)
        hand_end_y = 0.9 * np.sin(target_angle) - 0.3
        hand = Line(start=np.array([0, -0.3, 0]), end=np.array([hand_end_x, hand_end_y, 0]), color=YELLOW, stroke_width=3)

        # Animasi Render
        self.play(FadeIn(title), FadeIn(subtitle), Create(circle), FadeIn(center_dot), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(n, scale=0.5) for n in number_objects.values()], lag_ratio=0.05), run_time=0.8)
        self.play(GrowFromCenter(hand), run_time=0.5)
        
        for _ in range(2):
            self.play(number_objects[target_number].animate.set_color(RED), run_time=0.2)
            self.play(number_objects[target_number].animate.set_color(WHITE), run_time=0.2)

        self.wait(1.5)

def generate_captcha_gif(output_path: str):
    config.media_dir = "/tmp/manim_media"
    config.quality = "low_quality"
    config.pixel_width = 400
    config.pixel_height = 400
    config.frame_rate = 15
    config.output_file = "clock_captcha"
    config.format = "gif"
    
    scene = ClockCaptchaScene()
    scene.render()
    
    for root, dirs, files in os.walk("/tmp/manim_media"):
        for file in files:
            if file.endswith(".gif"):
                src = os.path.join(root, file)
                os.rename(src, output_path)
                return
