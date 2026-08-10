import os
import base64
import io
import urllib.request
import ssl
import numpy as np
import cv2
from PIL import Image
from typing import List, Tuple, Optional, Dict, Any

# Paths for SFace ONNX models
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models_data")
DETECTOR_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
RECOGNIZER_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

DETECTOR_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
RECOGNIZER_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

_detector = None
_recognizer = None
_haar_cascade = None

def _download_model_if_missing(url: str, path: str):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(url, context=context) as response, open(path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Warning: Could not download model from {url}: {e}")

def get_face_models():
    """Initializes and returns YuNet detector and SFace recognizer instances."""
    global _detector, _recognizer, _haar_cascade
    if _detector is None or _recognizer is None:
        _download_model_if_missing(DETECTOR_URL, DETECTOR_PATH)
        _download_model_if_missing(RECOGNIZER_URL, RECOGNIZER_PATH)
        
        if os.path.exists(DETECTOR_PATH) and os.path.exists(RECOGNIZER_PATH):
            _detector = cv2.FaceDetectorYN.create(DETECTOR_PATH, "", (300, 300), 0.5, 0.3, 5000)
            _recognizer = cv2.FaceRecognizerSF.create(RECOGNIZER_PATH, "")
        
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            _haar_cascade = cv2.CascadeClassifier(cascade_path)
        except Exception:
            _haar_cascade = None

    return _detector, _recognizer, _haar_cascade

def base64_to_cv2(base64_str: str) -> np.ndarray:
    """Decodes base64 string to OpenCV BGR image matrix."""
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    
    missing_padding = len(base64_str) % 4
    if missing_padding:
        base64_str += '=' * (4 - missing_padding)
        
    image_bytes = base64.b64decode(base64_str)
    image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

def extract_face_encoding(cv2_img: np.ndarray) -> Tuple[Optional[List[float]], int, str]:
    """
    Detects faces in OpenCV image using YuNet / Haar Cascade and extracts a 128-d SFace deep embedding vector.
    Returns: (128_dim_vector, face_count, status_message)
    """
    if cv2_img is None or cv2_img.size == 0:
        return None, 0, "Rasm bo'sh yoki noto'g'ri ko'rinishda."

    detector, recognizer, haar = get_face_models()
    h_img, w_img = cv2_img.shape[:2]

    # Resize image if extremely large for fast inference
    max_dim = 1024
    if max(h_img, w_img) > max_dim:
        scale = max_dim / float(max(h_img, w_img))
        cv2_img = cv2.resize(cv2_img, (int(w_img * scale), int(h_img * scale)))
        h_img, w_img = cv2_img.shape[:2]

    selected_face_landmark = None
    face_count = 0

    if detector is not None:
        detector.setInputSize((w_img, h_img))
        _, faces = detector.detect(cv2_img)
        if faces is not None and len(faces) > 0:
            face_count = len(faces)
            if face_count == 1:
                selected_face_landmark = faces[0]

    # Haar Cascade Fallback if YuNet detected 0 faces
    if face_count == 0 and haar is not None and not haar.empty():
        gray = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        detected_haar = haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(detected_haar) > 0:
            face_count = len(detected_haar)
            if face_count == 1:
                (x, y, w, h) = detected_haar[0]
                # Construct 15-element array expected by recognizer.alignCrop:
                # [x, y, w, h, x_re, y_re, x_le, y_le, x_n, y_n, x_rm, y_rm, x_lm, y_lm, score]
                selected_face_landmark = np.array([
                    x, y, w, h,
                    x + w * 0.3, y + h * 0.35,  # right eye
                    x + w * 0.7, y + h * 0.35,  # left eye
                    x + w * 0.5, y + h * 0.55,  # nose tip
                    x + w * 0.35, y + h * 0.75, # right mouth
                    x + w * 0.65, y + h * 0.75, # left mouth
                    0.99
                ], dtype=np.float32)

    if face_count == 0:
        return None, 0, "Rasmda yuz aniqlanmadi. Iltimos, yuzingizni kameraga to'g'ri qarating."
    if face_count > 1:
        return None, face_count, "Kamerada bir nechta yuz ko'rinmoqda. Faqat 1 ta yuz bo'lishi kerak."

    if selected_face_landmark is None:
        return None, 0, "Yuz aniqlashda xatolik yuz berdi."

    try:
        if recognizer is not None:
            aligned_face = recognizer.alignCrop(cv2_img, selected_face_landmark)
            feature = recognizer.feature(aligned_face)
            
            # Normalize embedding vector
            norm = np.linalg.norm(feature)
            if norm > 0:
                feature = feature / norm
                
            encoding_vector = feature.flatten().tolist()
            if len(encoding_vector) == 128:
                return encoding_vector, 1, "Face detected successfully"
    except Exception as e:
        print(f"SFace feature extraction error: {e}")

    return None, 0, "Yuz xususiyatlarini ajratib olishda xatolik yuz berdi."

def compare_face_encodings(
    query_encoding: List[float], 
    registered_encodings: List[List[float]],
    threshold: float = 0.42
) -> Tuple[float, bool, str]:
    """
    Compares a 128-d query face encoding against a list of 128-d registered encodings.
    Uses Cosine Similarity.
    Returns: (max_similarity_score, is_match, message)
    """
    if not registered_encodings:
        return 0.0, False, "Ushbu xodim uchun FaceID rasmi ro'yxatdan o'tmagan."

    if not query_encoding or len(query_encoding) != 128:
        return 0.0, False, "Kamera rasmidan olingan FaceID vektori noto'g mezonida."

    q_vec = np.array(query_encoding, dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    if q_norm == 0:
        return 0.0, False, "Kamera rasmi formati noto'g'ri."

    valid_scores = []
    for reg in registered_encodings:
        if not reg or len(reg) != 128:
            # Ignore legacy invalid encoding format (e.g. 192-d old histogram)
            continue

        r_vec = np.array(reg, dtype=np.float32)
        r_norm = np.linalg.norm(r_vec)
        if r_norm == 0:
            continue

        # Cosine similarity
        sim = float(np.dot(q_vec, r_vec) / (q_norm * r_norm))
        valid_scores.append(sim)

    if not valid_scores:
        return 0.0, False, "Bazada mos keladigan 128-o'lchamli FaceID topilmadi."

    best_score = max(valid_scores)
    confidence_score = round(float(best_score), 4)

    is_match = confidence_score >= threshold
    if is_match:
        msg = f"Yuz muvaffaqiyatli mos keldi ({confidence_score * 100:.1f}%)."
    else:
        msg = f"Yuz mos kelmadi ({confidence_score * 100:.1f}% < {threshold * 100:.1f}%)."

    return confidence_score, is_match, msg

def migrate_face_encodings(db):
    """
    Scans DB for legacy face encodings and re-extracts 128-d SFace embeddings from stored photos.
    """
    from app.models.domain import FaceEncoding, StoreSettings
    
    # 1. Update store settings threshold if still old 0.70 default
    store = db.query(StoreSettings).first()
    if store and (store.face_confidence_threshold > 0.60 or store.face_confidence_threshold < 0.35):
        store.face_confidence_threshold = 0.42
        db.commit()

    # 2. Re-encode face photos
    records = db.query(FaceEncoding).all()
    migrated = 0
    for item in records:
        if not item.encoding_data or len(item.encoding_data) != 128:
            if item.image_path:
                # Resolve full disk path
                full_path = item.image_path
                if full_path.startswith("/uploads/"):
                    full_path = os.path.join(BASE_DIR, item.image_path.lstrip("/"))
                elif full_path.startswith("uploads/"):
                    full_path = os.path.join(BASE_DIR, item.image_path)
                
                if os.path.exists(full_path):
                    img = cv2.imread(full_path)
                    if img is not None:
                        enc, count, _ = extract_face_encoding(img)
                        if enc and len(enc) == 128:
                            item.encoding_data = enc
                            migrated += 1
    if migrated > 0:
        db.commit()
        print(f"✓ Automatically migrated {migrated} face encodings to SFace 128-d embeddings.")


