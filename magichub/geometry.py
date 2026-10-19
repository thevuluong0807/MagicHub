"""Hình học vòng tròn: tính ô được chọn từ vector chuột. Thuần toán, không Qt."""
import math

R0, R1 = 58, 160  # bán kính: vùng chết ở tâm | mép ngoài của vòng duy nhất
R_MID = (R0 + R1) / 2  # kéo qua ngưỡng này trên một nhóm -> vòng đổi sang tác vụ của nhóm


def ring_arc(i: int, n: int) -> tuple[float, float]:
    """Cung (độ, chiều kim đồng hồ từ hướng 12h) của ô i trong n ô; ô 0 nằm giữa 12h."""
    s = 360 / n
    return i * s - s / 2, i * s + s / 2


def ring_hit(dx: float, dy: float, n: int) -> tuple[int | None, float]:
    """(ô dưới con trỏ, khoảng cách tới tâm); None nếu ở vùng chết. dy hướng xuống như toạ độ màn hình."""
    r = math.hypot(dx, dy)
    if n == 0 or r < R0:
        return None, r
    s = 360 / n
    a = (math.degrees(math.atan2(dx, -dy)) + s / 2) % 360
    return min(int(a // s), n - 1), r
