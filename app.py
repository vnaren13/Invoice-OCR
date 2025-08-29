import pytesseract
from PIL import Image
import re
from flask import Flask, request, jsonify, render_template
import os
from pdf2image import convert_from_bytes 

# Create a Flask web application
app = Flask(__name__)
POPPLER_PATH = r'C:\Program Files\poppler-25.07.0\Library\bin'


UPLOAD_FOLDER = 'uploads' 
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'} 

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Main Route to Render the HTML Page ---
@app.route('/')
def index():
    # Renders the index.html file from the 'templates' folder
    return render_template('index.html')

# --- OCR Upload and Processing Route ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename): 
        try:
            image = None
            # Check if the file is a PDF
            if file.mimetype == 'application/pdf':
                # Convert PDF to a list of PIL images (we only take the first page)
                # Ensure poppler_path is correctly set if poppler isn't in PATH
                # For Windows, you might need poppler_path=r'C:\Program Files\poppler-XXX\bin'
                images = convert_from_bytes(file.read(), first_page=1, last_page=1,  poppler_path=POPPLER_PATH)
                if images:
                    image = images[0]
                else:
                    return jsonify({'error': 'Could not convert PDF to image. Is poppler installed correctly?'}), 500
            else:
                # Assume it's an image file
                file.seek(0) # Ensure file pointer is at the beginning
                image = Image.open(file.stream)

            if not image:
                return jsonify({'error': 'No image could be processed from the uploaded file'}), 500

            # Step 2: Run OCR to extract text
            extracted_text = pytesseract.image_to_string(image)

            # Step 3: Try to extract useful business fields using regex
            invoice_number = re.search(r"Invoice\s*#?\s*(\w+)", extracted_text, re.IGNORECASE)
            total_amount = re.search(r"Total\s*[:]?\s*\$?([0-9,.]+)", extracted_text, re.IGNORECASE)
            due_date = re.search(r"Due Date[:]?\s*([\w\s,.-]+)", extracted_text, re.IGNORECASE)

            # Prepare the data to be sent back as JSON
            extracted_data = {
                'invoice_number': invoice_number.group(1) if invoice_number else 'Not found',
                'total_amount': total_amount.group(1) if total_amount else 'Not found',
                'due_date': due_date.group(1) if due_date else 'Not found',
                'full_text': extracted_text
            }
            
            return jsonify(extracted_data)

        except Exception as e:
            app.logger.error("Error during OCR processing", exc_info=True)
            return jsonify({'error': f'Server processing error: {str(e)}. Check server logs for details.'}), 500
    else: 
        return jsonify({'error': 'File type not allowed. Please upload a PNG, JPG, GIF, or PDF.'}), 400

# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)