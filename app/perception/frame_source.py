"""
Frame ingestion implementations for PHOENIX.
Provides OpenCV-based video file decoding and synthetic frame generators for testability.
"""

from pathlib import Path
from typing import Optional
import cv2
import numpy as np

from app.core.errors import PhoenixError
from app.domain.interfaces import FrameSource


class VideoFrameSource(FrameSource):
    """
    OpenCV video file frame source supporting recorded video files (MP4, AVI, MOV).
    Can also support live streams (RTSP, webcam) by passing device indices or stream URLs.
    """

    def __init__(self, source_path_or_uri: str, target_fps: Optional[float] = None, loop: bool = True) -> None:
        self.source_uri = str(source_path_or_uri)
        self.target_fps = target_fps
        self.loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_count: int = 0
        self._fps: float = 30.0
        self._open_capture()

    def _open_capture(self) -> None:
        """Open the video stream or file."""
        # Check if source is a numeric string (webcam index)
        if self.source_uri.isdigit():
            self._cap = cv2.VideoCapture(int(self.source_uri))
        else:
            self._cap = cv2.VideoCapture(self.source_uri)

        if not self._cap.isOpened():
            self._cap = None
            raise PhoenixError(f"Failed to open video source: {self.source_uri}")

        fps = self._cap.get(cv2.CAP_PROP_FPS)
        if fps and fps > 0:
            self._fps = fps
        if self.target_fps and self.target_fps > 0:
            self._fps = self.target_fps

    def read_frame(self) -> tuple[bool, Optional[np.ndarray], float]:
        """
        Read the next frame from the video source.
        Returns: (success: bool, frame: Optional[np.ndarray], timestamp_seconds: float)
        """
        if self._cap is None or not self._cap.isOpened():
            return False, None, 0.0

        success, frame = self._cap.read()
        if not success or frame is None:
            if self.loop and self._cap is not None:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = self._cap.read()
            if not success or frame is None:
                return False, None, 0.0

        self._frame_count += 1
        timestamp_seconds = (self._frame_count - 1) / self._fps
        return True, frame, timestamp_seconds
        return True, frame, timestamp_seconds

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def get_fps(self) -> float:
        return self._fps

    def get_frame_count(self) -> int:
        return self._frame_count

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class SyntheticFrameSource(FrameSource):
    """
    Synthetic frame source generating controllable dummy frames for unit testing and offline simulation.
    """

    def __init__(self, width: int = 640, height: int = 480, max_frames: int = 100, fps: float = 10.0) -> None:
        self.width = width
        self.height = height
        self.max_frames = max_frames
        self.fps = fps
        self._current_frame = 0
        self._is_opened = True

    def read_frame(self) -> tuple[bool, Optional[np.ndarray], float]:
        if not self._is_opened or self._current_frame >= self.max_frames:
            return False, None, 0.0

        # Generate a synthetic black/gray frame with frame counter timestamp watermark
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        self._current_frame += 1
        timestamp = (self._current_frame - 1) / self.fps
        return True, frame, timestamp

    def is_opened(self) -> bool:
        return self._is_opened and self._current_frame < self.max_frames

    def release(self) -> None:
        self._is_opened = False
