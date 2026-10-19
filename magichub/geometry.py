"""Hình học vòng tròn: tính ô được chọn từ vector chuột. Thuần toán, không Qt."""
import math

R0, R1, R2 = 48, 132, 272  # bán kính: vùng chết | hết vòng nhóm | hết vòng tác vụ


def group_arc(g: int, n: int) -> tuple[float, float]:
    """Cung (độ, chiều kim đồng hồ từ hướng 12h) của nhóm g trong n nhóm; nhóm 0 nằm giữa 12h."""
    s = 360 / n
    return g * s - s / 2, g * s + s / 2


def item_arc(g: int, n: int, i: int, cnt: int) -> tuple[float, float]:
    a0, a1 = group_arc(g, n)
    w = (a1 - a0) / cnt
    return a0 + i * w, a0 + (i + 1) * w


def hit(dx: float, dy: float, counts: list[int]) -> tuple[int | None, int | None]:
    """(nhóm, tác vụ) dưới con trỏ; dy hướng xuống như toạ độ màn hình."""
    n = len(counts)
    r = math.hypot(dx, dy)
    if n == 0 or r < R0:
        return None, None
    s = 360 / n
    a = (math.degrees(math.atan2(dx, -dy)) + s / 2) % 360
    g = min(int(a // s), n - 1)
    if r < R1 or counts[g] == 0:
        return g, None
    return g, min(int((a - g * s) // (s / counts[g])), counts[g] - 1)
