
import torch
import torch.nn as nn
import torchvision
from torchvision import transforms
from PIL import Image, ImageOps
import torch.nn.functional as F
import cv2
import numpy as np
import os

# --- Constants from the Training Script  ---
IMAGE_SIZE = 256
MAX_LEN = 10
CHECKPOINT_PATH = "Checkpoint.pth" # Make sure this file is in the same directory
special_char_list = ["<pad>"]
num_list = list('0123456789')
upper_alphabet_list = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')
lower_alphabet_list = list('abcdefghijklmnopqrstuvwxyz')
string_list = special_char_list + num_list + upper_alphabet_list + lower_alphabet_list
CHAR_NUM = len(string_list)
token_dictionary = {i: string_list[i] for i in range(len(string_list))}

# --- Model Definition ---
class LACC(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = torchvision.models.efficientnet_v2_m().features
        self.converter = nn.parameter.Parameter(torch.ones(64, CHAR_NUM))
        self.silu = nn.SiLU()
        self.linear1 = nn.Linear(1280, 512)
        self.linear2 = nn.Linear(512, 64)
        self.linear3 = nn.Linear(64, MAX_LEN)

    def forward(self, x):
        feature = self.encoder(x)
        feature = torch.flatten(feature, start_dim=2)
        feature = torch.matmul(feature, self.converter)
        y = feature.transpose(-1, -2)
        y = self.linear1(y)
        y = self.silu(y)
        y = self.linear2(y)
        y = self.silu(y)
        y = self.linear3(y)
        return y

# --- Image Transformation Pipeline ---
transformer = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
])

# --- Helper functions ---
def open_transparent_image(image_path):
    img = Image.open(image_path).convert("RGBA")
    white_bg = Image.new("RGBA", img.size, "WHITE")
    white_bg.paste(img, (0, 0), img)
    return white_bg.convert("RGB")

def apply_blur_and_contrast(image):
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    blurred_img = cv2.medianBlur(img_cv, 3)
    pil_blurred = Image.fromarray(cv2.cvtColor(blurred_img, cv2.COLOR_BGR2RGB))
    return ImageOps.autocontrast(pil_blurred)

# --- Global variables for the loaded model ---
# We define them here so they are loaded only once when the module is imported.
model = None
device = None

def _initialize_model():
    """Internal function to load the model and weights into memory."""
    global model, device
    if model is not None:
        return 

    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = LACC().to(device)
        
        if not os.path.exists(CHECKPOINT_PATH):
            raise FileNotFoundError(f"Checkpoint file not found at '{CHECKPOINT_PATH}'")
            
        checkpoint = torch.load(CHECKPOINT_PATH, map_location=device)
        model.load_state_dict(checkpoint['model_state_dict'])
        model.eval() # Set model to evaluation mode
        print("Captcha model loaded successfully.")
        
    except Exception as e:
        print(f"FATAL: Could not initialize CAPTCHA model: {e}")
        model = None # Ensure model is None if initialization fails

# --- THE MAIN FUNCTION TO BE CALLED FROM AUTOMATION SCRIPT of the IMMOScout bot---
def solve_captcha(image_path: str) -> str:
    """
    Takes the file path of a CAPTCHA image, solves it, and returns the text.
    
    Args:
        image_path: The path to the CAPTCHA image file.
        
    Returns:
        The predicted CAPTCHA text as a string, or an empty string if an error occurs.
    """
    if model is None:
        print("Error: CAPTCHA model is not initialized.")
        return ""

    try:
        # 1. Load and preprocess the image in memory
        base_image = open_transparent_image(image_path)
        processed_image = apply_blur_and_contrast(base_image)
        
        # 2. Convert to tensor for the model
        image_tensor = transformer(processed_image).unsqueeze(0).to(device)
        
        # 3. Predict
        with torch.no_grad():
            predict = model(image_tensor)
            
        predict = F.log_softmax(predict, dim=-2)
        predict_indices = torch.argmax(predict, dim=-2).squeeze(0).cpu().tolist()
        
        # 4. Decode the prediction and return the clean text
        predicted_text = "".join([token_dictionary.get(i, "") for i in predict_indices]).split("<pad>")[0]
        return predicted_text

    except Exception as e:
        print(f"An error occurred during CAPTCHA solving: {e}")
        return ""

# --- Initialize the model once when this script is imported or run ---
_initialize_model()


# --- Test Block ---
# This code only runs if you execute "python prediction.py" directly.
# It's for testing the solve_captcha function.
if __name__ == "__main__":
    # Create a dummy image for testing if it doesn't exist
    TEST_IMAGE_PATH = "image.png"
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f"'{TEST_IMAGE_PATH}' not found. Please place a CAPTCHA image with this name in the directory to test.")
    else:
        print(f"--- Testing CAPTCHA Solver with '{TEST_IMAGE_PATH}' ---")
        solution = solve_captcha(TEST_IMAGE_PATH)
        
        # This will print ONLY the final solution, as requested.
        print(solution)