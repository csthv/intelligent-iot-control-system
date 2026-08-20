"""Optional DeepFace verification utility for captured ESP32-CAM images.

This is the repository-ready form of the supplied `Face_Rec.py`: paths are no
longer hard-coded and the tool can compare any query image against every image
in a reference directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from deepface import DeepFace

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def verify_against_directory(query_image: Path, reference_dir: Path) -> tuple[bool, Path | None]:
    references = sorted(
        p for p in reference_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not references:
        raise FileNotFoundError(f"No reference images found in {reference_dir}")

    for reference in references:
        result = DeepFace.verify(
            img1_path=str(query_image),
            img2_path=str(reference),
            enforce_detection=True,
        )
        if bool(result.get("verified")):
            return True, reference
    return False, None


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a face against reference images.")
    parser.add_argument("query_image", type=Path, help="Captured/query image")
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=Path("data/reference_faces"),
        help="Directory containing authorized/reference faces",
    )
    args = parser.parse_args()

    matched, reference = verify_against_directory(args.query_image, args.reference_dir)
    if matched:
        print(f"Faces match. Reference: {reference}")
    else:
        print("Faces do not match.")


if __name__ == "__main__":
    main()
