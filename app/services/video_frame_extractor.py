"""
Servico de extracao de frames de video para preview.

Usa OpenCV para extrair frames individuais de videos.
Thread-safe e reutiliza VideoCaptures para performance.
"""

import base64
import threading
from pathlib import Path
from typing import Dict, Optional

import cv2


class VideoFrameExtractor:
    """
    Extrai frames de video para preview.

    Singleton thread-safe que reutiliza VideoCaptures
    para evitar abrir o mesmo arquivo multiplas vezes.
    """

    _captures: Dict[str, cv2.VideoCapture] = {}
    _lock = threading.RLock()

    @classmethod
    def extract_frame(cls, video_path: str, timestamp: float) -> Optional[str]:
        """
        Extrai frame em timestamp e retorna como base64 PNG.

        Args:
            video_path: Caminho para o arquivo de video
            timestamp: Tempo em segundos para extrair o frame

        Returns:
            String base64 do frame em formato PNG, ou None se falhar
        """
        with cls._lock:
            # Reutilizar VideoCapture se ja existir
            if video_path not in cls._captures:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return None
                cls._captures[video_path] = cap

            cap = cls._captures[video_path]

            # Calcular numero do frame baseado no timestamp
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # Fallback

            frame_num = int(timestamp * fps)

            # Ir para o frame desejado
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            success, frame = cap.read()

            if not success:
                return None

            # Redimensionar para preview (128x128)
            frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_AREA)

            # Encode para PNG e base64
            _, buffer = cv2.imencode('.png', frame)
            return base64.b64encode(buffer).decode('utf-8')

    @classmethod
    def release(cls, video_path: str) -> None:
        """
        Libera VideoCapture de um video especifico.

        Args:
            video_path: Caminho do video para liberar
        """
        with cls._lock:
            if video_path in cls._captures:
                cls._captures[video_path].release()
                del cls._captures[video_path]

    @classmethod
    def release_all(cls) -> None:
        """Libera todos os VideoCaptures."""
        with cls._lock:
            for cap in cls._captures.values():
                cap.release()
            cls._captures.clear()

    @classmethod
    def get_video_info(cls, video_path: str) -> Optional[Dict]:
        """
        Obtem informacoes basicas do video.

        Args:
            video_path: Caminho para o arquivo de video

        Returns:
            Dict com fps, frame_count, duration, width, height
        """
        with cls._lock:
            if video_path not in cls._captures:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    return None
                cls._captures[video_path] = cap

            cap = cls._captures[video_path]

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            duration = frame_count / fps if fps > 0 else 0

            return {
                "fps": fps,
                "frame_count": frame_count,
                "duration": duration,
                "width": width,
                "height": height
            }
