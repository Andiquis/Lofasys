#!/usr/bin/env python3
"""
Motor Biométrico Facial - InsightFace (ArcFace)
Script externo ejecutable con soporte completo de GUI (cv2.imshow).
Se invoca desde el notebook vía subprocess para evitar problemas de kernel.

Uso:
    python face_engine.py register <username>
    python face_engine.py login <username>
    python face_engine.py info <username>
    python face_engine.py list
    python face_engine.py delete <username>
"""

import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
import os
import json
import sys
import time
from datetime import datetime

# ===================== CONFIGURACIÓN =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

# Umbrales de calidad
BLUR_THRESHOLD = 80.0
BRIGHTNESS_MIN = 50
BRIGHTNESS_MAX = 200
MIN_FACE_RATIO = 0.08
CENTER_TOLERANCE = 0.25

# Umbrales de similaridad
MATCH_THRESHOLD = 0.45
GRAY_ZONE_MIN = 0.35
MAX_LOGIN_ATTEMPTS = 3

# Registro
MIN_CAPTURES = 8
MAX_CAPTURES = 15
REGISTER_TIMEOUT = 12
CAPTURE_INTERVAL = 0.4

# Cámara
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Colores BGR
GREEN = (0, 255, 0)
RED = (0, 0, 255)
YELLOW = (0, 255, 255)
WHITE = (255, 255, 255)
CYAN = (255, 255, 0)
ORANGE = (0, 165, 255)


# ===================== MODELO =====================
def load_model():
    """Carga el modelo InsightFace buffalo_l."""
    print("🔄 Cargando modelo InsightFace (buffalo_l)...")
    start = time.time()
    face_app = FaceAnalysis(
        name='buffalo_l',
        root=os.path.join(BASE_DIR, "models"),
        providers=['CPUExecutionProvider']
    )
    face_app.prepare(ctx_id=0, det_size=(640, 640))
    elapsed = time.time() - start
    print(f"✅ Modelo cargado en {elapsed:.1f}s")
    return face_app


# ===================== VALIDACIÓN DE CALIDAD =====================
def check_blur(face_img):
    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    return laplacian_var >= BLUR_THRESHOLD, laplacian_var

def check_brightness(face_img):
    gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    ok = BRIGHTNESS_MIN <= mean_brightness <= BRIGHTNESS_MAX
    return ok, mean_brightness

def check_face_size(bbox, frame_shape):
    h, w = frame_shape[:2]
    face_w = bbox[2] - bbox[0]
    face_h = bbox[3] - bbox[1]
    ratio = (face_w * face_h) / (w * h)
    return ratio >= MIN_FACE_RATIO, ratio

def check_face_centered(bbox, frame_shape):
    h, w = frame_shape[:2]
    face_cx = (bbox[0] + bbox[2]) / 2
    face_cy = (bbox[1] + bbox[3]) / 2
    dx = abs(face_cx - w / 2) / w
    dy = abs(face_cy - h / 2) / h
    return dx < CENTER_TOLERANCE and dy < CENTER_TOLERANCE, (dx, dy)

def validate_face(face, frame):
    messages = []
    all_ok = True
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    face_img = frame[y1:y2, x1:x2]

    if face_img.size == 0:
        return False, ["Rostro fuera de cuadro"]

    ok, val = check_blur(face_img)
    if not ok:
        messages.append(f"Imagen borrosa ({val:.0f})")
        all_ok = False

    ok, val = check_brightness(face_img)
    if not ok:
        msg = "oscuro" if val < BRIGHTNESS_MIN else "sobreexpuesto"
        messages.append(f"Muy {msg} ({val:.0f})")
        all_ok = False

    ok, val = check_face_size(bbox, frame.shape)
    if not ok:
        messages.append(f"Acerquese mas ({val*100:.1f}%)")
        all_ok = False

    ok, (dx, dy) = check_face_centered(bbox, frame.shape)
    if not ok:
        messages.append("Centre su rostro en el ovalo")
        all_ok = False

    if all_ok:
        messages.append("Calidad OK")

    return all_ok, messages


# ===================== LIVENESS =====================
class LivenessDetector:
    def __init__(self):
        self.blink_count = 0
        self.prev_ear = None
        self.blink_consec_frames = 2
        self.blink_counter = 0
        self.prev_nose_pos = None
        self.movement_detected = False
        self.movement_threshold = 8.0

    def eye_aspect_ratio(self, landmarks):
        left_eye = landmarks[0]
        right_eye = landmarks[1]
        nose = landmarks[2]
        eye_dist = np.linalg.norm(left_eye - right_eye)
        left_nose = np.linalg.norm(left_eye - nose)
        right_nose = np.linalg.norm(right_eye - nose)
        return (left_nose + right_nose) / (2.0 * eye_dist + 1e-6)

    def detect_blink(self, landmarks):
        ear = self.eye_aspect_ratio(landmarks)
        if self.prev_ear is not None:
            ear_diff = self.prev_ear - ear
            if ear_diff > 0.02:
                self.blink_counter += 1
            else:
                if self.blink_counter >= self.blink_consec_frames:
                    self.blink_count += 1
                self.blink_counter = 0
        self.prev_ear = ear
        return self.blink_count > 0

    def detect_movement(self, landmarks):
        nose = landmarks[2]
        if self.prev_nose_pos is not None:
            dist = np.linalg.norm(nose - self.prev_nose_pos)
            if dist > self.movement_threshold:
                self.movement_detected = True
        self.prev_nose_pos = nose.copy()
        return self.movement_detected

    def check_liveness(self, landmarks):
        blink_ok = self.detect_blink(landmarks)
        movement_ok = self.detect_movement(landmarks)
        is_alive = blink_ok or movement_ok
        status = []
        status.append(f"Parpadeo: {'OK' if blink_ok else 'parpadee'}")
        status.append(f"Movimiento: {'OK' if movement_ok else 'mueva la cabeza'}")
        return is_alive, status


# ===================== EMBEDDINGS =====================
def compute_average_embedding(embeddings):
    if not embeddings:
        return None
    avg = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg)
    if norm > 0:
        avg = avg / norm
    return avg

def cosine_similarity(emb1, emb2):
    dot = np.dot(emb1, emb2)
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)
    return dot / (norm1 * norm2 + 1e-6)

def cosine_distance(emb1, emb2):
    return 1.0 - cosine_similarity(emb1, emb2)

def save_profile(username, embedding, num_captures):
    filepath = os.path.join(PROFILES_DIR, f"{username}.npz")
    metadata = {
        "username": username,
        "created": datetime.now().isoformat(),
        "num_captures": int(num_captures),
        "login_count": 0,
        "update_weight": 5
    }
    np.savez(filepath, embedding=embedding, metadata=json.dumps(metadata))
    return filepath

def load_profile(username):
    filepath = os.path.join(PROFILES_DIR, f"{username}.npz")
    if not os.path.exists(filepath):
        return None, None
    data = np.load(filepath, allow_pickle=True)
    embedding = data['embedding']
    metadata = json.loads(str(data['metadata']))
    return embedding, metadata

def update_profile_adaptive(username, new_embedding):
    embedding, metadata = load_profile(username)
    if embedding is None:
        return False
    k = metadata.get('update_weight', 5)
    updated = (embedding * k + new_embedding) / (k + 1)
    norm = np.linalg.norm(updated)
    if norm > 0:
        updated = updated / norm
    metadata['login_count'] = metadata.get('login_count', 0) + 1
    metadata['last_login'] = datetime.now().isoformat()
    metadata['update_weight'] = min(k + 1, 20)
    filepath = os.path.join(PROFILES_DIR, f"{username}.npz")
    np.savez(filepath, embedding=updated, metadata=json.dumps(metadata))
    return True

def list_profiles():
    return [f.replace('.npz', '') for f in os.listdir(PROFILES_DIR) if f.endswith('.npz')]


# ===================== DIBUJO VISUAL =====================
def draw_face_guide(frame, color=WHITE, thickness=2):
    h, w = frame.shape[:2]
    center = (w // 2, h // 2 - 20)
    axes = (int(w * 0.22), int(h * 0.35))
    cv2.ellipse(frame, center, axes, 0, 0, 360, color, thickness)
    line_len = 15
    cx, cy = center
    cv2.line(frame, (cx - line_len, cy), (cx + line_len, cy), color, 1)
    cv2.line(frame, (cx, cy - line_len), (cx, cy + line_len), color, 1)
    return center, axes

def draw_face_bbox(frame, face, color=GREEN):
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    corner_len = 20
    t = 2
    cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, t)
    cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, t)
    cv2.line(frame, (x2, y1), (x2 - corner_len, y1), color, t)
    cv2.line(frame, (x2, y1), (x2, y1 + corner_len), color, t)
    cv2.line(frame, (x1, y2), (x1 + corner_len, y2), color, t)
    cv2.line(frame, (x1, y2), (x1, y2 - corner_len), color, t)
    cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, t)
    cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, t)
    if hasattr(face, 'det_score'):
        cv2.putText(frame, f"{face.det_score:.2f}",
                    (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

def draw_status_panel(frame, messages, y_start=30):
    overlay = frame.copy()
    panel_h = 25 + len(messages) * 25
    cv2.rectangle(overlay, (5, 5), (380, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
    y = y_start
    for msg in messages:
        color = GREEN if "OK" in msg else (YELLOW if "parpadee" in msg or "mueva" in msg else RED)
        cv2.putText(frame, msg, (15, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        y += 25

def draw_progress_bar(frame, current, total, y_pos=None):
    h, w = frame.shape[:2]
    if y_pos is None:
        y_pos = h - 40
    bar_w = int(w * 0.6)
    bar_x = (w - bar_w) // 2
    bar_h = 20
    cv2.rectangle(frame, (bar_x, y_pos), (bar_x + bar_w, y_pos + bar_h), (50, 50, 50), -1)
    progress = min(current / total, 1.0)
    fill_w = int(bar_w * progress)
    color = GREEN if progress >= 1.0 else CYAN
    cv2.rectangle(frame, (bar_x, y_pos), (bar_x + fill_w, y_pos + bar_h), color, -1)
    text = f"Capturas: {current}/{total}"
    cv2.putText(frame, text, (bar_x + 5, y_pos + 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1, cv2.LINE_AA)
    cv2.rectangle(frame, (bar_x, y_pos), (bar_x + bar_w, y_pos + bar_h), WHITE, 1)

def draw_countdown(frame, seconds_left):
    h, w = frame.shape[:2]
    text = f"{seconds_left:.0f}s"
    cv2.putText(frame, text, (w - 70, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, YELLOW, 2, cv2.LINE_AA)

def draw_result_overlay(frame, text, color=GREEN):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, h//2 - 50), (w, h//2 + 50), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    font_scale = 1.2
    thickness = 3
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    x = (w - tw) // 2
    y = h // 2 + th // 2
    cv2.putText(frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness, cv2.LINE_AA)


# ===================== REGISTRO =====================
def register_face(username, face_app):
    print(f"📷 Iniciando registro para: {username}")
    print("🎯 Coloque su rostro dentro del óvalo. Parpadee y mueva ligeramente la cabeza.")
    print("⌨️  Presione 'q' para cancelar.\n")

    existing, _ = load_profile(username)
    if existing is not None:
        print(f"⚠️  Ya existe un perfil para '{username}'. Se sobreescribirá.")

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    if not cap.isOpened():
        print("❌ Error: No se pudo abrir la cámara")
        return {"success": False, "message": "No se pudo abrir la cámara"}

    liveness = LivenessDetector()
    embeddings = []
    last_capture_time = 0
    start_time = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            elapsed = time.time() - start_time
            remaining = REGISTER_TIMEOUT - elapsed

            if remaining <= 0:
                if len(embeddings) >= MIN_CAPTURES:
                    break
                else:
                    draw_result_overlay(frame, "TIEMPO AGOTADO", RED)
                    cv2.imshow("Registro Facial", frame)
                    cv2.waitKey(2000)
                    return {"success": False, "message": f"Tiempo agotado. Solo {len(embeddings)}/{MIN_CAPTURES} capturas."}

            if len(embeddings) >= MAX_CAPTURES:
                break

            faces = face_app.get(frame)
            guide_color = RED
            status_msgs = [f"Registro: {username}"]

            if len(faces) == 0:
                status_msgs.append("No se detecta rostro")
            elif len(faces) > 1:
                status_msgs.append("Multiples rostros detectados")
            else:
                face = faces[0]
                quality_ok, quality_msgs = validate_face(face, frame)
                status_msgs.extend(quality_msgs)

                bbox_color = YELLOW if not quality_ok else GREEN
                draw_face_bbox(frame, face, bbox_color)

                if quality_ok:
                    guide_color = YELLOW
                    if face.kps is not None:
                        alive, live_msgs = liveness.check_liveness(face.kps)
                        status_msgs.extend(live_msgs)

                        if alive:
                            guide_color = GREEN
                            now = time.time()
                            if now - last_capture_time >= CAPTURE_INTERVAL:
                                if face.embedding is not None:
                                    emb = face.embedding / (np.linalg.norm(face.embedding) + 1e-6)
                                    embeddings.append(emb)
                                    last_capture_time = now
                                    status_msgs.append(f"Captura #{len(embeddings)}")
                    else:
                        status_msgs.append("Verificando liveness...")
                        guide_color = YELLOW

            draw_face_guide(frame, guide_color, 2)
            draw_status_panel(frame, status_msgs)
            draw_progress_bar(frame, len(embeddings), MIN_CAPTURES)
            draw_countdown(frame, max(0, remaining))

            cv2.imshow("Registro Facial", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                return {"success": False, "message": "Cancelado por el usuario"}

    finally:
        cap.release()
        cv2.destroyAllWindows()

    if len(embeddings) < MIN_CAPTURES:
        return {"success": False, "message": f"Capturas insuficientes: {len(embeddings)}/{MIN_CAPTURES}"}

    avg_embedding = compute_average_embedding(embeddings)
    filepath = save_profile(username, avg_embedding, len(embeddings))
    total_time = time.time() - start_time

    result = {
        "success": True,
        "username": username,
        "num_captures": len(embeddings),
        "embedding_dim": len(avg_embedding),
        "profile_path": filepath,
        "processing_time_s": round(total_time, 1)
    }
    return result


# ===================== LOGIN =====================
def login_face(username, face_app):
    print(f"🔐 Iniciando login para: {username}")

    profile_emb, metadata = load_profile(username)
    if profile_emb is None:
        return {"match": False, "message": f"No existe perfil para '{username}'"}

    print(f"📋 Perfil cargado - Logins previos: {metadata.get('login_count', 0)}")
    print("🎯 Coloque su rostro dentro del óvalo.")
    print("⌨️  Presione 'q' para cancelar.\n")

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    if not cap.isOpened():
        return {"match": False, "message": "No se pudo abrir la cámara"}

    liveness = LivenessDetector()
    attempts = 0
    best_score = 0
    start_time = time.time()
    login_timeout = 15
    result = None
    verified_frames = 0
    required_verified = 3

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            elapsed = time.time() - start_time
            remaining = login_timeout - elapsed

            if remaining <= 0:
                draw_result_overlay(frame, "TIEMPO AGOTADO", RED)
                cv2.imshow("Login Facial", frame)
                cv2.waitKey(2000)
                result = {"match": False, "score": best_score, "message": "Tiempo agotado"}
                break

            faces = face_app.get(frame)
            guide_color = RED
            status_msgs = [f"Login: {username} | Intento {attempts + 1}/{MAX_LOGIN_ATTEMPTS}"]
            current_score = 0

            if len(faces) == 0:
                status_msgs.append("No se detecta rostro")
                verified_frames = 0
            elif len(faces) > 1:
                status_msgs.append("Multiples rostros")
                verified_frames = 0
            else:
                face = faces[0]
                quality_ok, quality_msgs = validate_face(face, frame)
                status_msgs.extend(quality_msgs)
                draw_face_bbox(frame, face, YELLOW)

                if quality_ok and face.embedding is not None:
                    guide_color = YELLOW

                    alive = True
                    if face.kps is not None:
                        alive, live_msgs = liveness.check_liveness(face.kps)
                        status_msgs.extend(live_msgs)

                    emb = face.embedding / (np.linalg.norm(face.embedding) + 1e-6)
                    dist = cosine_distance(emb, profile_emb)
                    sim = cosine_similarity(emb, profile_emb)
                    current_score = max(sim, 0)
                    best_score = max(best_score, current_score)

                    score_color = GREEN if dist < MATCH_THRESHOLD else (YELLOW if dist < GRAY_ZONE_MIN else RED)
                    status_msgs.append(f"Similaridad: {current_score:.3f} (dist: {dist:.3f})")

                    if dist < MATCH_THRESHOLD:
                        guide_color = GREEN
                        verified_frames += 1
                        status_msgs.append(f"Match! ({verified_frames}/{required_verified})")

                        if verified_frames >= required_verified:
                            draw_face_guide(frame, GREEN, 3)
                            draw_face_bbox(frame, face, GREEN)
                            draw_status_panel(frame, status_msgs)
                            draw_result_overlay(frame, f"ACCESO CONCEDIDO - {current_score:.2f}", GREEN)
                            cv2.imshow("Login Facial", frame)
                            cv2.waitKey(2000)

                            update_profile_adaptive(username, emb)

                            result = {
                                "match": True,
                                "score": float(current_score),
                                "liveness": alive,
                                "quality_ok": True,
                                "timestamp": datetime.now().isoformat(),
                                "processing_time_ms": int((time.time() - start_time) * 1000),
                                "confidence_level": "high" if current_score > 0.6 else "medium"
                            }
                            break
                    elif dist < GRAY_ZONE_MIN + 0.15:
                        guide_color = YELLOW
                        status_msgs.append("Zona gris - Ajuste posicion")
                        verified_frames = 0
                    else:
                        guide_color = RED
                        verified_frames = 0
                        status_msgs.append("No coincide")

                    # Score bar visual
                    h, w = frame.shape[:2]
                    bar_w = int(w * 0.5)
                    bar_x = (w - bar_w) // 2
                    bar_y = h - 70
                    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 20), (50, 50, 50), -1)
                    fill = int(bar_w * min(current_score, 1.0))
                    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill, bar_y + 20), score_color, -1)
                    cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + 20), WHITE, 1)
                    thresh_x = bar_x + int(bar_w * (1 - MATCH_THRESHOLD))
                    cv2.line(frame, (thresh_x, bar_y - 5), (thresh_x, bar_y + 25), WHITE, 2)
                    cv2.putText(frame, f"Score: {current_score:.3f}",
                                (bar_x, bar_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, WHITE, 1)

            draw_face_guide(frame, guide_color, 2)
            draw_status_panel(frame, status_msgs)
            draw_countdown(frame, max(0, remaining))

            cv2.imshow("Login Facial", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                result = {"match": False, "score": best_score, "message": "Cancelado"}
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()

    if result is None:
        result = {"match": False, "score": float(best_score), "message": "Sin resultado"}

    return result


# ===================== UTILIDADES =====================
def show_profile_info(username):
    emb, meta = load_profile(username)
    if emb is None:
        return {"error": f"No existe perfil para '{username}'"}
    return {
        "username": username,
        "created": meta.get('created', 'N/A'),
        "num_captures": meta.get('num_captures', 'N/A'),
        "login_count": meta.get('login_count', 0),
        "last_login": meta.get('last_login', 'Nunca'),
        "embedding_shape": list(emb.shape),
        "embedding_dtype": str(emb.dtype)
    }

def delete_profile(username):
    filepath = os.path.join(PROFILES_DIR, f"{username}.npz")
    if os.path.exists(filepath):
        os.remove(filepath)
        return {"deleted": True, "username": username}
    return {"deleted": False, "message": f"No existe perfil '{username}'"}


# ===================== MAIN =====================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Uso: python face_engine.py <register|login|info|list|delete> [username]"}))
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "list":
        profiles = list_profiles()
        print(json.dumps({"profiles": profiles, "count": len(profiles)}))
        sys.exit(0)

    if action in ("register", "login", "info", "delete") and len(sys.argv) < 3:
        print(json.dumps({"error": f"Se requiere username para '{action}'"}))
        sys.exit(1)

    username = sys.argv[2] if len(sys.argv) > 2 else None

    if action == "info":
        result = show_profile_info(username)
        print(json.dumps(result, ensure_ascii=False))

    elif action == "delete":
        result = delete_profile(username)
        print(json.dumps(result, ensure_ascii=False))

    elif action == "register":
        face_app = load_model()
        result = register_face(username, face_app)
        # Print JSON result as last line for parsing
        print(f"\n__RESULT_JSON__:{json.dumps(result, ensure_ascii=False)}")

    elif action == "login":
        face_app = load_model()
        result = login_face(username, face_app)
        print(f"\n__RESULT_JSON__:{json.dumps(result, ensure_ascii=False)}")

    elif action == "gui":
        # Lanzar la interfaz gráfica Tkinter
        gui_path = os.path.join(BASE_DIR, "face_gui.py")
        os.execvp(sys.executable, [sys.executable, gui_path])

    else:
        print(json.dumps({"error": f"Acción desconocida: {action}"}))
        sys.exit(1)
