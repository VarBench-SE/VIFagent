import base64
from io import BytesIO
from PIL import Image
import numpy as np

def encode_image(image_path: str):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def encode_image(image: Image.Image):
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

def mse(image1:Image.Image, image2:Image.Image):
    """Compute Mean Squared Error between two PIL images."""
    arr1 = np.array(image1, dtype=np.float32)
    arr2 = np.array(image2, dtype=np.float32)

    if arr1.shape != arr2.shape:
        raise ValueError("Images must have the same dimensions")

    return np.mean((arr1 - arr2) ** 2)

def adjust_bbox(box, image: Image.Image):
    adjust = lambda box_k, cursize: (box_k / 1000) * cursize
    box_2d = box["box_2d"]
    new_box = (
        int(adjust(box_2d[1], image.width)),
        int(adjust(box_2d[0], image.height)),
        int(adjust(box_2d[3], image.width)),
        int(adjust(box_2d[2], image.height)),
    )
    box["box_2d"] = new_box
    return box