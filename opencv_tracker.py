"""OpenCV 기반 HSV 마커 추적 유틸리티.

웹 UI는 지연을 줄이기 위해 Canvas/ImageData 경로를 사용하지만, 같은
추적 로직을 서버/오프라인 파이프라인에서 OpenCV로 실행할 수 있게 둔다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class BlobTrack:
    x: float
    y: float
    area: int
    confidence: float


def track_hsv_blob(
    frame_bgr: np.ndarray,
    hsv_ranges: Iterable[tuple[tuple[int, int, int], tuple[int, int, int]]],
    seed: tuple[float, float] | None = None,
    min_area: int = 24,
) -> BlobTrack | None:
    """BGR 프레임에서 HSV 범위에 맞는 가장 신뢰도 높은 blob 중심을 반환한다."""
    import cv2  # type: ignore

    if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
        raise ValueError("frame_bgr must be a BGR image with shape HxWx3")

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in hsv_ranges:
        lo_arr = np.array(lo, dtype=np.uint8)
        hi_arr = np.array(hi, dtype=np.uint8)
        mask |= cv2.inRange(hsv, lo_arr, hi_arr)

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best: BlobTrack | None = None
    best_score = -float("inf")
    for label in range(1, n):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        component = labels == label
        moments = cv2.moments(component.astype(np.uint8), binaryImage=True)
        if abs(moments["m00"]) < 1e-9:
            continue
        x = float(moments["m10"] / moments["m00"])
        y = float(moments["m01"] / moments["m00"])
        confidence = float(mask[component].mean() / 255.0)
        score = area * 0.5 + confidence * 100.0
        if seed is not None:
            score += max(0.0, 160.0 - np.hypot(x - seed[0], y - seed[1]))
        if score > best_score:
            best_score = score
            best = BlobTrack(x=x, y=y, area=area, confidence=confidence)
    return best
