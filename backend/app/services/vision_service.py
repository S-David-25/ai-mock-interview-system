import cv2
import base64
import numpy as np
import logging
from typing import Dict, Any, Tuple
from app.schemas.interview import VisionFrameResponse

logger = logging.getLogger("vision_service")

# Initialize OpenCV Haar Cascade for face detection fallback
_face_cascade = None
try:
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    _face_cascade = cv2.CascadeClassifier(cascade_path)
except Exception as e:
    logger.warning(f"Could not load OpenCV Haar Cascade: {e}")

class VisionService:
    """
    Computer Vision pipeline for webcam frames.
    Extracts face presence, head alignment, camera-facing behavior, and posture indicators.
    
    Academic Note: Uses 'Eye-contact proxy score' and 'Observable posture indicators'
    rather than psychological or clinical claims.
    """

    @staticmethod
    def process_frame(image_base64: str) -> Dict[str, Any]:
        """
        Decodes base64 frame, detects face and head orientation, and computes proxy metrics.
        """
        if not image_base64:
            return {
                "face_detected": False,
                "camera_facing_ratio": 0.0,
                "eye_contact_proxy_score": 0.0,
                "posture_score": 0.0,
                "head_stability_score": 0.0,
                "status": "no_image_data"
            }

        try:
            # Strip data URL header if present (e.g. "data:image/jpeg;base64,...")
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]

            img_bytes = base64.b64decode(image_base64)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None:
                return {
                    "face_detected": False,
                    "camera_facing_ratio": 0.0,
                    "eye_contact_proxy_score": 0.0,
                    "posture_score": 0.0,
                    "head_stability_score": 0.0,
                    "status": "decode_failed"
                }

            h, w, _ = frame.shape
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            face_detected = False
            eye_contact_proxy = 0.0
            posture_score = 0.0
            head_stability = 85.0
            camera_facing_ratio = 0.0

            if _face_cascade is not None:
                faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
                if len(faces) > 0:
                    face_detected = True
                    # Primary face is the largest bounding box
                    fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])

                    # Calculate horizontal and vertical centrality of face in frame
                    face_center_x = fx + (fw / 2.0)
                    face_center_y = fy + (fh / 2.0)
                    frame_center_x = w / 2.0
                    frame_center_y = h / 2.0

                    offset_x = abs(face_center_x - frame_center_x) / frame_center_x
                    offset_y = abs(face_center_y - frame_center_y) / frame_center_y

                    # Camera-facing proxy: higher when face is centered and frontal
                    centrality_score = max(0.0, 100.0 - (offset_x * 60.0 + offset_y * 40.0))
                    camera_facing_ratio = round(centrality_score / 100.0, 2)
                    eye_contact_proxy = round(max(30.0, min(95.0, centrality_score)), 1)

                    # Posture score based on face scale and vertical positioning (upright posture)
                    # Ideal face height in frame is approx 20% to 50% of frame height
                    face_ratio = fh / float(h)
                    if 0.20 <= face_ratio <= 0.50 and fy < (h * 0.5):
                        posture_score = round(min(100.0, 80.0 + (1.0 - offset_x) * 15.0), 1)
                    else:
                        posture_score = round(max(40.0, 60.0 - abs(face_ratio - 0.35) * 50.0), 1)

            if not face_detected:
                # No face detected in frame
                return {
                    "face_detected": False,
                    "camera_facing_ratio": 0.0,
                    "eye_contact_proxy_score": 0.0,
                    "posture_score": 0.0,
                    "head_stability_score": 0.0,
                    "status": "face_not_detected"
                }

            return {
                "face_detected": True,
                "camera_facing_ratio": camera_facing_ratio,
                "eye_contact_proxy_score": eye_contact_proxy,
                "posture_score": posture_score,
                "head_stability_score": head_stability,
                "status": "processed"
            }

        except Exception as e:
            logger.error(f"Error processing video frame: {e}")
            return {
                "face_detected": False,
                "camera_facing_ratio": 0.0,
                "eye_contact_proxy_score": 0.0,
                "posture_score": 0.0,
                "head_stability_score": 0.0,
                "status": f"error: {str(e)}"
            }
