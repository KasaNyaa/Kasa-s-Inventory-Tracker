from PIL import Image, ImageEnhance
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def image_to_text(image_path: str) -> str:
    """Run OCR on an image file and return extracted text."""

    with Image.open(image_path) as img:
        # Make the image larger
        scale = 2
        img = img.resize(
            (img.width * scale, img.height * scale)
        )

        # Convert to grayscale
        img = img.convert("L")

        # Increase contrast
        img = ImageEnhance.Contrast(img).enhance(2)

        # Tell Tesseract to look for multiple lines of text
        text = pytesseract.image_to_string(
            img,
            config="--psm 6"
        )

    return text