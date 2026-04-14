import requests
import base64

from PIL import Image
from io import BytesIO


def generate_image_with_input_image(
    api_key: str,
    input_image_path: str,
    output_image_path: str,
    prompt: str,
    style: str = "default",
    width: int = 256,
    height: int = 256,
    strength: float = 0.5,
    seed: int = 0
):
    # 1. Convert local image to Base64 and convert to RGB
    with Image.open(input_image_path) as img:
        rgb_img = img.convert('RGB')
        buffer = BytesIO()
        rgb_img.save(buffer, format='PNG')
        base64_input_image = base64.b64encode(buffer.getvalue()).decode('utf-8')

    # 2. Prepare the request
    url = "https://api.retrodiffusion.ai/v1/inferences"
    method = "POST"
    headers = {
        "X-RD-Token": api_key,
    }

    payload = {
        "prompt": prompt,
        "prompt_style": style,
        "model": model,
        "width": width,
        "height": height,
        "input_image": base64_input_image,
        "strength": strength,
        "num_images": 1,
        "seed": seed
    }

    # 3. Send the request
    response = requests.request(method, url, headers=headers, json=payload)

    # 4. Handle response
    if response.status_code == 200:
        data = response.json()
        # data['base64_images'] is a list of base64-encoded image strings
        base64_images = data.get("base64_images", [])
        if base64_images:
            # Take the first image
            img_data = base64_images[0]
            # Decode and save
            with open(output_image_path, "wb") as out_file:
                out_file.write(base64.b64decode(img_data))
            print(f"Image generated and saved to {output_image_path}")
        else:
            print("No images returned by the API.")
    else:
        print(f"Request failed with status code {response.status_code}: {response.text}")


if __name__ == "__main__":
    # Example usage
    YOUR_API_KEY = "rdpk-xxxxxxxxxxxx"  # Replace with your actual API key
    INPUT_IMAGE_PATH = "input.png"  # Replace with your local input image path
    OUTPUT_IMAGE_PATH = "generated_image.png"  # Where you want to save the result

    generate_image_with_input_image(
        api_key=YOUR_API_KEY,
        input_image_path=INPUT_IMAGE_PATH,
        output_image_path=OUTPUT_IMAGE_PATH,
        prompt="an orange sports car",
        width=256,
        height=256,
        strength=0.75,
        seed = 1
    )