import os
import sys
import io
from flask import Flask, render_template, request, redirect, url_for, jsonify
from keras.models import load_model
from werkzeug.utils import secure_filename
from PIL import Image
import numpy as np
from groq import Groq

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

app = Flask(__name__)

model = load_model('model/AppDermAIModel.keras')

UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

labels = ['Chickenpox', 'Measles', 'Monkeypox', 'Normal']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def preprocess_image(image_path):
    image = Image.open(image_path)
    image = image.resize((224, 224))
    image = np.array(image)
    image = image / 255.0
    image = np.expand_dims(image, axis=0)
    return image

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            return render_template('index.html', error="Please select a file before uploading.")

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            try:
                preprocessed_image = preprocess_image(file_path)
                prediction = model.predict(preprocessed_image)
                predicted_index = np.argmax(prediction, axis=1)[0]
                predicted_label = labels[predicted_index]

                client = Groq(api_key="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")
                chat_completion = client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": f"Give a one-line suggestion for managing {predicted_label} skin disease.",
                    }],
                    model="llama3-8b-8192",
                    stream=False,
                )

                suggestions = chat_completion.choices[0].message.content[:150]

                initial_message = f"{suggestions}"

                return redirect(url_for('result', uploaded_image=filename, prediction=predicted_label, initial_message=initial_message))

            except Exception as e:
                return render_template('index.html', error=f"An error occurred: {str(e)}")

        else:
            return render_template('index.html', error="Unsupported file type. Please upload a PNG, JPG, JPEG, or GIF image.")

    return render_template('index.html')

@app.route('/result')
def result():
    uploaded_image = request.args.get('uploaded_image')
    prediction = request.args.get('prediction')
    initial_message = request.args.get('initial_message')
    uploaded_image_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_image)
    return render_template('result.html', uploaded_image=uploaded_image_path, prediction=prediction, initial_message=initial_message)

@app.route('/chatbot', methods=['POST'])
def chatbot():
    try:
        data = request.get_json()
        user_message = data.get('question')
        prediction = data.get('prediction')

        client = Groq(api_key="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")
        chat_completion = client.chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"Answer the following question regarding {prediction} skin disease: {user_message}",
            }],
            model="llama3-8b-8192",
            stream=False,
        )

        ai_message = chat_completion.choices[0].message.content

        return jsonify({'response': ai_message})

    except Exception as e:
        return jsonify({'response': f"An error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    app.run(debug=False, host="0.0.0.0", port=5000)
