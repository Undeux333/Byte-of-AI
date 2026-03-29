import os
import textwrap
from PIL import Image, ImageDraw, ImageFont

# ── フォントパス (GitHub Actions Ubuntu / ローカル両対応) ────────────────
def _get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── テキスト折り返し ──────────────────────────────────────────────────────
def _wrap(draw: ImageDraw.Draw, text: str, font, max_width: int) -> list[str]:
    words  = text.split()
    lines  = []
    line   = []
    for word in words:
        test = " ".join(line + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] <= max_width:
            line.append(word)
        else:
            if line:
                lines.append(" ".join(line))
            line = [word]
    if line:
        lines.append(" ".join(line))
    return lines


# ── メインカード生成 ──────────────────────────────────────────────────────
def create_card(
    headline: str,
    simple_explanation: str,
    emoji: str,
    category: str,
    color_hex: str,
    source: str = "",
) -> str:
    """
    1200×675px の解説カード画像を生成して IMAGE_FILE に保存。
    保存したパスを返す。
    """
    W, H = 1200, 675
    os.makedirs("data", exist_ok=True)
    out_path = "data/card.png"

    # ── ベース色 ──────────────────────────────────────────────────
    try:
        base_color = tuple(int(color_hex.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        base_color = (44, 62, 80)

    dark_bg   = tuple(max(0, c - 60) for c in base_color)
    accent    = base_color

    img  = Image.new("RGB", (W, H), dark_bg)
    draw = ImageDraw.Draw(img)

    # ── 上部アクセントバー ────────────────────────────────────────
    draw.rectangle([0, 0, W, 12], fill=accent)

    # ── 右上: 大きな絵文字ゾーン (背景円) ─────────────────────────
    circle_x, circle_y, circle_r = 1080, 120, 90
    draw.ellipse(
        [circle_x - circle_r, circle_y - circle_r, circle_x + circle_r, circle_y + circle_r],
        fill=tuple(min(255, c + 40) for c in base_color)
    )
    font_emoji = _get_font(72, bold=False)
    draw.text((circle_x, circle_y), emoji, font=font_emoji,
              anchor="mm", fill="white")

    # ── カテゴリバッジ ────────────────────────────────────────────
    badge_text = category.upper()
    font_badge = _get_font(22, bold=True)
    bx, by = 48, 36
    bbox   = draw.textbbox((bx, by), badge_text, font=font_badge)
    draw.rectangle([bx - 10, by - 6, bbox[2] + 10, bbox[3] + 6],
                   fill=accent)
    draw.text((bx, by), badge_text, font=font_badge, fill="white")

    # ── ヘッドライン ──────────────────────────────────────────────
    font_hl  = _get_font(58, bold=True)
    hl_lines = _wrap(draw, headline, font_hl, W - 140)
    yl = 110
    for line in hl_lines[:3]:
        draw.text((48, yl), line, font=font_hl, fill="white")
        yl += 68

    # ── 区切り線 ──────────────────────────────────────────────────
    sep_y = yl + 20
    draw.rectangle([48, sep_y, W - 48, sep_y + 3], fill=tuple(min(255, c + 80) for c in base_color))

    # ── 解説ボックス (白背景) ─────────────────────────────────────
    box_y1 = sep_y + 24
    box_y2 = H - 70
    draw.rectangle([32, box_y1, W - 32, box_y2], fill=(255, 255, 255), outline=(220, 220, 220), width=1)

    # 「わかりやすく解説」ラベル
    font_label = _get_font(20, bold=True)
    draw.text((56, box_y1 + 16), "EXPLAINED SIMPLY", font=font_label, fill=accent)

    # 解説テキスト
    font_exp = _get_font(30, bold=False)
    exp_lines = _wrap(draw, simple_explanation, font_exp, W - 130)
    ye = box_y1 + 56
    for line in exp_lines[:5]:
        draw.text((56, ye), line, font=font_exp, fill=(30, 30, 30))
        ye += 40

    # ── フッター ──────────────────────────────────────────────────
    font_footer = _get_font(20, bold=False)
    footer_text = f"Source: {source}" if source else "Powered by AI"
    draw.text((48, H - 44), footer_text, font=font_footer,
              fill=tuple(min(255, c + 120) for c in base_color))
    draw.text((W - 48, H - 44), "AI News Bot", font=font_footer,
              fill=tuple(min(255, c + 120) for c in base_color), anchor="ra")

    img.save(out_path, "PNG")
    return out_path
