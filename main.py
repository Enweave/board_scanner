import os

from modules.app import ScannerApp
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    CAMERA_INDEX = int(os.getenv("WEBCAM_INDEX", 0))
    IMAGE_PATH = os.getenv("STILL_IMAGE_PATH", None)
    FPS = int(os.getenv("FPS_LIMIT", 30))
    USE_STILL_IMAGE = os.getenv("USE_STILL", False)

    if USE_STILL_IMAGE:
        app = ScannerApp(still_image=IMAGE_PATH, fps_limit=FPS)
    else:
        app = ScannerApp(webcam_index=CAMERA_INDEX, fps_limit=FPS)

    app.run()
