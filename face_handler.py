import os
import json
import urllib.request
import cv2
import numpy as np

class FaceHandler:
    def __init__(self, base_dir=".", model_dir="models", image_dir="images", users_file="users.json"):
        self.base_dir = os.path.abspath(base_dir)
        self.model_dir = os.path.join(self.base_dir, model_dir)
        self.image_dir = os.path.join(self.base_dir, image_dir)
        self.cache_dir = os.path.join(self.image_dir, "cache")
        self.users_file = os.path.join(self.base_dir, users_file)
        
        # Ensure directories exist
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Model paths
        self.detector_path = os.path.join(self.model_dir, "face_detection_yunet_2023mar.onnx")
        self.recognizer_path = os.path.join(self.model_dir, "face_recognition_sface_2021dec.onnx")
        
        # Download models if they don't exist
        self._ensure_models_exist()
        
        # Initialize OpenCV Face Detector and Recognizer
        self._init_models()
        
        # Load user database and precompute embeddings
        self.users = {}
        self.known_embeddings = {}
        self.load_users_and_embeddings()

    def _ensure_models_exist(self):
        """Downloads the ONNX model files from OpenCV's repository if they are missing."""
        detector_url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        recognizer_url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
        
        if not os.path.exists(self.detector_path):
            print(f"Downloading YuNet Face Detector model to {self.detector_path}...")
            try:
                urllib.request.urlretrieve(detector_url, self.detector_path)
                print("YuNet model downloaded successfully.")
            except Exception as e:
                print(f"Error downloading YuNet model: {e}")
                
        if not os.path.exists(self.recognizer_path):
            print(f"Downloading SFace Face Recognizer model to {self.recognizer_path} (approx. 36MB)...")
            try:
                urllib.request.urlretrieve(recognizer_url, self.recognizer_path)
                print("SFace model downloaded successfully.")
            except Exception as e:
                print(f"Error downloading SFace model: {e}")

    def _init_models(self):
        """Initializes the YuNet and SFace models using OpenCV DNN."""
        if not os.path.exists(self.detector_path) or not os.path.exists(self.recognizer_path):
            raise FileNotFoundError("Required face detection/recognition model files are missing.")
        
        # Initialize face detector (YuNet). We set default input size to (320, 320)
        # It will be dynamically adjusted during processing based on input image sizes.
        self.detector = cv2.FaceDetectorYN.create(
            model=self.detector_path,
            config="",
            input_size=(320, 320),
            score_threshold=0.8,
            nms_threshold=0.3,
            top_k=5000,
            backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
            target_id=cv2.dnn.DNN_TARGET_CPU
        )
        
        # Initialize face recognizer (SFace)
        self.recognizer = cv2.FaceRecognizerSF.create(
            model=self.recognizer_path,
            config="",
            backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
            target_id=cv2.dnn.DNN_TARGET_CPU
        )

    def load_users_and_embeddings(self):
        """Loads registered users and extracts/loads their face embeddings."""
        # Load user metadata
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    self.users = json.load(f)
            except Exception as e:
                print(f"Error reading users file: {e}")
                self.users = {}
        else:
            self.users = {}
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f)
        
        # Load embeddings
        self.known_embeddings = {}
        for user_id in self.users:
            image_path = os.path.join(self.image_dir, f"{user_id}.jpg")
            cache_path = os.path.join(self.cache_dir, f"{user_id}.npy")
            
            if os.path.exists(cache_path):
                # Load cached embedding
                try:
                    self.known_embeddings[user_id] = np.load(cache_path)
                    continue
                except Exception as e:
                    print(f"Error loading cached embedding for {user_id}: {e}")
            
            if os.path.exists(image_path):
                # Compute embedding and cache it
                print(f"Generating embedding for {self.users[user_id]['name']}...")
                img = cv2.imread(image_path)
                if img is not None:
                    feat = self._extract_embedding_from_image(img)
                    if feat is not None:
                        self.known_embeddings[user_id] = feat
                        np.save(cache_path, feat)
                    else:
                        print(f"Warning: No face detected in registered image for user {user_id}")
                else:
                    print(f"Warning: Could not read image for user {user_id}")

    def _extract_embedding_from_image(self, img):
        """Helper to detect a single face and extract its embedding."""
        h, w = img.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(img)
        
        if faces is not None and len(faces) > 0:
            # Align and crop the first detected face
            face_align = self.recognizer.alignCrop(img, faces[0])
            # Extract 128-D feature embedding
            feat = self.recognizer.feature(face_align)
            return feat
        return None

    def register_user(self, user_id, name, department, email, frame):
        """Registers a user with their metadata and face frame."""
        # Check if face is detected in the provided frame
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        
        if faces is None or len(faces) == 0:
            return False, "No face detected in the image. Please try again."
        if len(faces) > 1:
            return False, "Multiple faces detected. Please make sure only one person is in the frame."
        
        # Align and crop
        face_align = self.recognizer.alignCrop(frame, faces[0])
        # Extract feature
        feat = self.recognizer.feature(face_align)
        
        # Save original frame as the user's registry image
        image_path = os.path.join(self.image_dir, f"{user_id}.jpg")
        cv2.imwrite(image_path, frame)
        
        # Save embedding to cache
        cache_path = os.path.join(self.cache_dir, f"{user_id}.npy")
        np.save(cache_path, feat)
        
        # Add to local tracking
        self.known_embeddings[user_id] = feat
        
        # Update user metadata
        from datetime import datetime
        self.users[user_id] = {
            "name": name,
            "department": department,
            "email": email,
            "registered_on": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=4)
            
        return True, "User registered successfully."

    def delete_user(self, user_id):
        """Deletes a registered user, their metadata, saved image, and embedding cache."""
        if user_id in self.users:
            del self.users[user_id]
            with open(self.users_file, 'w') as f:
                json.dump(self.users, f, indent=4)
                
            if user_id in self.known_embeddings:
                del self.known_embeddings[user_id]
                
            # Remove files
            image_path = os.path.join(self.image_dir, f"{user_id}.jpg")
            cache_path = os.path.join(self.cache_dir, f"{user_id}.npy")
            if os.path.exists(image_path):
                os.remove(image_path)
            if os.path.exists(cache_path):
                os.remove(cache_path)
                
            return True, f"User {user_id} deleted."
        return False, "User not found."

    def detect_and_recognize(self, frame, threshold=0.363):
        """Detects and matches all faces in the frame.
        
        Returns a list of dictionaries with bounding boxes, names, and confidence scores.
        """
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        
        results = []
        if faces is not None:
            for face in faces:
                # face format: [x1, y1, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rc, y_rc, x_lc, y_lc, score]
                box = list(map(int, face[0:4]))
                
                # Crop and align face
                face_align = self.recognizer.alignCrop(frame, face)
                # Feature extraction
                feat = self.recognizer.feature(face_align)
                
                best_match = "Unknown"
                best_score = -1.0
                
                # Compare with known faces
                for user_id, known_feat in self.known_embeddings.items():
                    # Cosine similarity matching
                    score = self.recognizer.match(feat, known_feat, cv2.FaceRecognizerSF_FR_COSINE)
                    if score > best_score:
                        best_score = score
                        best_match = user_id
                
                # Filter by similarity threshold (SFace cosine match threshold is typically 0.363)
                if best_score < threshold:
                    matched_id = "Unknown"
                    matched_name = "Unknown"
                else:
                    matched_id = best_match
                    matched_name = self.users.get(matched_id, {}).get("name", "Unknown")
                
                results.append({
                    "box": box,
                    "user_id": matched_id,
                    "name": matched_name,
                    "score": float(best_score)
                })
        return results

if __name__ == "__main__":
    # Test initialization
    print("Testing FaceHandler initialization...")
    try:
        handler = FaceHandler()
        print("Success! Models loaded.")
        print(f"Registered users: {len(handler.users)}")
    except Exception as e:
        print(f"Initialization failed: {e}")
