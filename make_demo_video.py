"""Generate a terminal-style demo video from the actual prototype execution output."""
import subprocess, os
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
W, H = 1280, 720
BG = (18, 22, 30)
FG = (220, 224, 230)
GREEN = (80, 200, 120)
YELLOW = (240, 200, 80)
RED = (240, 100, 100)
BLUE = (120, 180, 255)
GRAY = (130, 140, 150)
CYAN = (80, 220, 220)
PURPLE = (200, 140, 255)

def color_for(line):
    if line.startswith("  [OK]") or "✓" in line: return GREEN
    if line.startswith("  [FAIL]") or "✗" in line: return RED
    if "[ADAPT]" in line: return YELLOW
    if "GOAL:" in line: return PURPLE
    if "UNDERSTAND" in line or "PLAN" in line: return BLUE
    if "EXECUTE" in line: return CYAN
    if "STEP" in line: return GRAY
    if "===" in line or "RESULT" in line: return (255, 255, 255)
    return FG

def render(lines, max_visible=28):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 20)
        title_font = ImageFont.truetype(FONT_BOLD, 28)
        small_font = ImageFont.truetype(FONT_PATH, 15)
    except Exception:
        font = title_font = small_font = ImageFont.load_default()
    d.rectangle([0, 0, W, 44], fill=(35, 42, 55))
    d.text((16, 10), "autonomous-ai-task-worker  —  CentrAlign AI prototype demo", font=title_font, fill=CYAN)
    d.ellipse([W-30, 14, W-18, 26], fill=(255, 95, 86))
    d.ellipse([W-50, 14, W-38, 26], fill=(255, 189, 46))
    d.ellipse([W-70, 14, W-58, 26], fill=(39, 201, 63))
    shown = lines[-max_visible:]
    y = 58
    for line in shown:
        d.text((16, y), line, font=font, fill=color_for(line))
        y += 21
    d.rectangle([0, H-30, W, H], fill=(28, 34, 46))
    d.text((16, H-24), "Goal -> Understand -> Plan -> Execute -> Observe -> Adapt -> Verify -> Complete",
           font=small_font, fill=GRAY)
    return img

def main():
    proc = subprocess.run(
        ["python3", "invoice_task.py"],
        capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
    out = (proc.stdout + proc.stderr).replace("\r", "")
    lines = [l for l in out.split("\n")]
    os.makedirs("demo_frames", exist_ok=True)
    total = len(lines)
    max_visible = 28
    frame_idx = 0
    # Hold final frame for 40 frames
    for i in range(1, total + 1):
        for repeat in range(3):  # 3 frames per line
            img = render(lines[:i], max_visible)
            img.save(f"demo_frames/f_{frame_idx:04d}.png")
            frame_idx += 1
    for _ in range(50):
        img = render(lines, max_visible)
        img.save(f"demo_frames/f_{frame_idx:04d}.png")
        frame_idx += 1
    print(f"Generated {frame_idx} frames from {total} output lines")

if __name__ == "__main__":
    main()
