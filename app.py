import pytesseract
from PIL import Image, ImageOps
import re
from flask import Flask, request, jsonify, render_template
import os
from pdf2image import convert_from_bytes
import base64
import io


app = Flask(__name__)
POPPLER_PATH = None # Update if your path is different
if os.name == 'nt': # 'nt' is for Windows
    POPPLER_PATH = r'C:\Program Files\poppler-25.07.0\Library\bin'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_image_from_file(file):
    """Helper function to get a PIL Image from an uploaded file (image or PDF)."""
    image = None
    if file.mimetype == 'application/pdf':
        images = convert_from_bytes(file.read(), first_page=1, last_page=1, poppler_path=POPPLER_PATH)
        if images:
            image = images[0]
    else:
        file.seek(0)
        image = Image.open(file.stream)
    return image

# --- Main Route to Render the HTML Page ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Step 1: Pre-processing Route ---
@app.route('/preprocess', methods=['POST'])
def preprocess_image():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file'}), 400
    
    try:
        image = get_image_from_file(file)
        if not image: return jsonify({'error': 'Could not process file into image'}), 500

        preprocessed_image = ImageOps.grayscale(image).convert('1')
        buffered = io.BytesIO()
        preprocessed_image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return jsonify({'preprocessed_image': f'data:image/png;base64,{img_str}'})
    except Exception as e:
        app.logger.error("Error during pre-processing", exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- Step 2: Character Recognition Route ---
@app.route('/recognize', methods=['POST'])
def recognize_text():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file'}), 400

    try:
        image = get_image_from_file(file)
        if not image: return jsonify({'error': 'Could not process file into image'}), 500
        
        # This step just extracts the raw text
        raw_text = pytesseract.image_to_string(image)
        return jsonify({'raw_text': raw_text})
    except Exception as e:
        app.logger.error("Error during recognition", exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- Step 3: Final Field Extraction Route ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if not file or not allowed_file(file.filename): return jsonify({'error': 'Invalid file'}), 400
    
    try:
        # Re-extract the text here to keep endpoints independent
        image = get_image_from_file(file)
        if not image: return jsonify({'error': 'Could not process file into image'}), 500
        extracted_text = pytesseract.image_to_string(image)

        invoice_number = re.search(r"Invoice\s*#?\s*(\w+)", extracted_text, re.IGNORECASE)
        total_amount = re.search(r"Total\s*[:]?\s*\$?([0-9,.]+)", extracted_text, re.IGNORECASE)
        due_date = re.search(r"Due Date[:]?\s*([\w\s,.-]+)", extracted_text, re.IGNORECASE)

        extracted_data = {
            'invoice_number': invoice_number.group(1) if invoice_number else 'Not found',
            'total_amount': total_amount.group(1) if total_amount else 'Not found',
            'due_date': due_date.group(1) if due_date else 'Not found',
            'full_text': extracted_text
        }
        
        return jsonify(extracted_data)
    except Exception as e:
        app.logger.error("Error during OCR processing", exc_info=True)
        return jsonify({'error': f'Server processing error: {str(e)}. Check server logs.'}), 500

# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)