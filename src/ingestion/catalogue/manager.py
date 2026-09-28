import json
from pathlib import Path
from typing import List

from .models import Camera


class CatalogueManager:

    def __init__(self, departments_dir: str):
        self.departments_dir = Path(departments_dir)

    def load_department_catalogue(self, file_path: Path) -> List[Camera]:
        """
        Load cameras from one department registry.
        """

        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        cameras = []

        for camera_data in data.get("cameras", []):
            cameras.append(Camera(**camera_data))

        return cameras

    def load_all_cameras(self) -> List[Camera]:
        """
        Load cameras from every department registry.
        """

        all_cameras: List[Camera] = []

        if not self.departments_dir.exists():
            return all_cameras

        for file_path in sorted(self.departments_dir.glob("*.json")):

            try:
                cameras = self.load_department_catalogue(file_path)
                all_cameras.extend(cameras)

                print(
                    f"[CATALOGUE] Loaded "
                    f"{len(cameras)} cameras from {file_path.name}"
                )

            except Exception as error:
                print(
                    f"[CATALOGUE] Failed to load "
                    f"{file_path.name}: {error}"
                )

        return all_cameras

    def get_live_cameras(self) -> List[Camera]:
        """
        Return only cameras currently marked as live.
        """

        cameras = self.load_all_cameras()

        return [
            camera
            for camera in cameras
            if camera.live
        ]

    def get_camera(self, camera_id: str) -> Camera | None:
        """
        Find a camera by camera_id.
        """

        cameras = self.load_all_cameras()

        for camera in cameras:
            if camera.camera_id == camera_id:
                return camera

        return None