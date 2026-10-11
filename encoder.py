"""
=============================================================================
 ROS Attendance Bot — Face Encoder
 Scans dataset/ folder, computes 128-d face embeddings, saves to .pkl
 Usage: python encoder.py  [--rebuild]
=============================================================================
Dataset folder structure:
    dataset/
        John_Doe_001/
            img1.jpg
            img2.jpg
        Jane_Smith_002/
            img1.jpg
=============================================================================
"""

import os
import pickle
import argparse
import logging
from pathlib import Path

import cv2
import face_recognition
import numpy as np

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(config.LOGS_DIR, "encoder.log")),
    ],
)
log = logging.getLogger(__name__)


def parse_name_id(folder_name: str):
    """
    Folder name format: FirstName_LastName_ID  (e.g. 'John_Doe_001')
    Returns (full_name, student_id)
    """
    parts = folder_name.rsplit("_", 1)
    if len(parts) == 2:
        name = parts[0].replace("_", " ")
        sid  = parts[1]
    else:
        name = folder_name.replace("_", " ")
        sid  = "N/A"
    return name, sid


def encode_faces(rebuild: bool = False):
    """
    Walk through dataset/, encode each face, save to ENCODINGS_FILE.
    Returns: dict with keys 'encodings', 'names', 'ids'
    """
    enc_path = Path(config.ENCODINGS_FILE)
    enc_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing if available and not rebuilding
    if enc_path.exists() and not rebuild:
        log.info("Loading existing encodings from %s", enc_path)
        with open(enc_path, "rb") as f:
            return pickle.load(f)

    known_encodings = []
    known_names     = []
    known_ids       = []

    dataset_path = Path(config.DATASET_DIR)
    if not dataset_path.exists():
        dataset_path.mkdir(parents=True)
        log.warning("Dataset directory was empty. Add subject folders to dataset/")
        return {"encodings": [], "names": [], "ids": []}

    person_folders = sorted([d for d in dataset_path.iterdir() if d.is_dir()])
    log.info("Found %d person folders in dataset/", len(person_folders))

    for person_dir in person_folders:
        name, sid = parse_name_id(person_dir.name)
        images    = list(person_dir.glob("*.jpg")) + list(person_dir.glob("*.png")) + list(person_dir.glob("*.jpeg"))

        if not images:
            log.warning("No images found in %s — skipping", person_dir.name)
            continue

        person_encodings = []
        for img_path in images:
            img_bgr = cv2.imread(str(img_path))
            if img_bgr is None:
                log.warning("Could not read %s", img_path)
                continue

            # Downsample if photo is high-res (e.g. phone camera) to save RAM/CPU on Pi 4B
            max_dim = max(img_bgr.shape[:2])
            if max_dim > 640:
                s = 640.0 / max_dim
                img_bgr = cv2.resize(img_bgr, (0, 0), fx=s, fy=s)

            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            boxes   = face_recognition.face_locations(img_rgb, model=config.DETECTION_MODEL,
                                                      number_of_times_to_upsample=config.UPSAMPLE_TIMES)
            encs    = face_recognition.face_encodings(img_rgb, boxes)

            if encs:
                person_encodings.append(encs[0])
                log.debug("  ✓ encoded %s", img_path.name)
            else:
                log.warning("  ✗ No face in %s", img_path.name)

        if person_encodings:
            # Average encoding for robustness
            avg_enc = np.mean(person_encodings, axis=0)
            known_encodings.append(avg_enc)
            known_names.append(name)
            known_ids.append(sid)
            log.info("  Encoded '%s' (ID: %s) — %d image(s)", name, sid, len(person_encodings))

    data = {"encodings": known_encodings, "names": known_names, "ids": known_ids}
    with open(enc_path, "wb") as f:
        pickle.dump(data, f)

    log.info("Saved %d face encodings → %s", len(known_encodings), enc_path)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encode faces from dataset/")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild encodings")
    args = parser.parse_args()
    encode_faces(rebuild=args.rebuild)
    print("✅ Encoding complete!")
