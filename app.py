# app.py
import os
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from google.cloud import speech_v1p1beta1 as speech
from google.cloud import storage
import razorpay
import traceback
from urllib.parse import unquote
import logging
import dotenv

# --- CONDITIONAL LOGIC FOR LOCAL DEVELOPMENT ---
# Cloud Run automatically sets the K_SERVICE environment variable.
# We check for its absence to load the .env file only when running locally.
if os.environ.get('K_SERVICE') is None:
    dotenv.load_dotenv()
    logging.info("Running locally - .env file loaded.")


# --- Configure logging at the top of your file ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Flask App Initialization ---
app = Flask(__name__,
            template_folder='templates',
            static_folder='static')
CORS(app)

# --- Razorpay Configuration ---
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_WprqVAEObL47N8')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'ry9HrZPWRGdxKWGCHCZA0TqO')

try:
    razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    logger.info("Razorpay client initialized.")
except Exception as e:
    logger.error(f"Error initializing Razorpay client. Please check your keys: {e}", exc_info=True)
    razorpay_client = None

# --- Google Cloud Storage & STT Configuration ---
GCS_BUCKET_NAME = 'donotdeletechand1'
USER_DATA_FOLDER = 'user_data'

try:
    storage_client = storage.Client()
    gcs_bucket = storage_client.bucket(GCS_BUCKET_NAME)
    logger.info(f"Google Cloud Storage client initialized for bucket: {GCS_BUCKET_NAME}")
except Exception as e:
    logger.error("Error initializing Google Cloud Storage client. Please check authentication and bucket name.", exc_info=True)
    storage_client = None
    gcs_bucket = None

# --- Helper function to convert URL to GCS URI ---
def convert_to_gcs_uri(http_url):
    """Converts a public GCS HTTP URL to a gs:// URI."""
    if http_url.startswith("https://storage.googleapis.com/"):
        gcs_path = http_url[len("https://storage.googleapis.com/"):]
        parts = gcs_path.split("/", 1)
        if len(parts) == 2:
            bucket_name = parts[0]
            object_path = parts[1]
            return f"gs://{bucket_name}/{object_path}"
    return None

# --- SERVER-SIDE "DATABASE" (IN REAL APP: USE A PROPER DB) ---
SERVER_BOOK_DATABASE = {
    101: {
        "id": 101,
        "title": "Kadapa Story",
        "author": "విశ్వనాథరెడ్డి",
        "language": "Telugu",
        "category": "Self-Help",
        "rating": 4.8,
        "cover": "https://c4.wallpaperflare.com/wallpaper/102/104/18/woody-in-toy-story-3-hd-toy-story-3-woody-illustration-wallpaper-preview.jpg",
        "audioSrc": "https://storage.googleapis.com/donotdeletechand1/telugu-story.mp3",
        "textSummary": "కడప ఫ్యాక్షన్ కథలు అంటే రాయలసీమలో, ముఖ్యంగా కడప ప్రాంతంలో తరతరాలుగా కుటుంబాల మధ్య జరిగే ఆధిపత్య పోరాటాలు, ప్రతీకారాలు, పరువు హత్యలు, భూవివాదాలు వంటి వాస్తవ ఘటనల ఆధారంగా అల్లుకున్న కథలు. ఇవి ఆ ప్రాంతపు మాండలికం, సంప్రదాయాలతో కూడి వాస్తవికతకు దగ్గరగా ఉంటాయి.",
        "keyTakeaways": ["ఆధిపత్య పోరాటాలు", "ప్రతీకార కథలు", "మాండలిక వర్ణన"],
        "transcript": [
            {"time": 0.0, "text": "కడప ఫ్యాక్షన్ కథలు అంటే రాయలసీమలో,"},
            {"time": 2.8, "text": "ముఖ్యంగా కడప ప్రాంతంలో తరతరాలుగా కుటుంబాల మధ్య జరిగే ఆధిపత్య పోరాటాలు,"},
            {"time": 7.5, "text": "ప్రతీకారాలు, పరువు హత్యలు, భూవివాదాలు వంటి వాస్తవ ఘటనల ఆధారంగా "},
            {"time": 13.5, "text": "అల్లుకున్న కథలు.ఇవి ఆ ప్రాంతపు మాండలికం, సంప్రదాయాలతో కూడి వాస్తవికతకు దగ్గరగా ఉంటాయి."}
        ]
    },
    102: {
        "id": 102,
        "title": "Sapiens",
        "author": "Yuval Noah Harari",
        "language": "English",
        "category": "History",
        "rating": 4.7,
        "cover": "https://c4.wallpaperflare.com/wallpaper/127/164/7/kid-luffy-monkey-d-luffy-one-piece-anime-hd-wallpaper-preview.jpg",
        "audioSrc": "https://storage.googleapis.com/donotdeletechand1/monkey-the-luffy.mp3",
        "textSummary": "A brief history of humankind, from the Stone Age to the present.",
        "keyTakeaways": ["Cognitive Revolution", "Agricultural Revolution"],
        "transcript":
        [
            {"time": 0.0, "text": "Monkey D. Luffy, inspired by pirate Shanks,"},
            {"time": 2.5, "text": "gained a rubber body from a Devil Fruit"},
            {"time": 4.8, "text": "and vowed to become King of the Pirates."},
            {"time": 7.3, "text": "He set sail at 17, gathering a loyal crew: the Straw Hat Pirates,"},
            {"time": 12.0, "text": "each chasing their own dreams."},
            {"time": 14.0, "text": "Together, they journeyed the perilous Grand Line,"},
            {"time": 18.0, "text": "challenging powerful Warlords, Marine Admirals, and even Emperors."},
            {"time": 23.5, "text": "Luffy's signature \"Gear\" techniques and unwavering resolve helped them overcome countless, stronger foes."},
            {"time": 30.0, "text": "Post-timeskip, he mastered Haki, significantly boosting his power."},
            {"time": 34.5, "text": "Their most recent battles culminated in the liberation of Wano from an Emperor."},
            {"time": 40.0, "text": "There, Luffy awakened his Devil Fruit's true power, transforming into \"Gear Fifth.\""},
            {"time": 46.5, "text": "Now recognized as an Emperor himself, he sails onward."},
            {"time": 50.0, "text": "His ultimate goal: find the One Piece and usher in an era of true freedom."}
        ]
    },
    201: {
        "id": 201,
        "title": "Atomic Habits",
        "author": "James Clear",
        "language": "Hindi",
        "category": "Self-Help",
        "rating": 4.9,
        "cover": "https://c4.wallpaperflare.com/wallpaper/479/712/924/movie-mr-bean-holiday-mr-bean-wallpaper-preview.jpg",
        "audioSrc": "https://storage.googleapis.com/donotdeletechand1/Hindi-voices/book_201_Atomic_Habits.mp3",
        "textSummary": "Aadat banane aur todne ke prabhavi tarike.",
        "keyTakeaways": ["Chhote sudhar", "System banayein"],
        "transcript": []
    },
    301: {
        "id": 301,
        "title": "Ponniyin Selvan",
        "author": "Kalki Krishnamurthy",
        "language": "Tamil",
        "category": "History",
        "rating": 4.9,
        "cover": "https://c4.wallpaperflare.com/wallpaper/532/459/698/crayon-shin-chan-cartoon-night-dog-hd-wallpaper-preview.jpg",
        "audioSrc": "https://storage.googleapis.com/donotdeletechand1/Tamil voices/book_301_Ponniyin_Selvan.mp3",
        "textSummary": "A historical novel centered on the Chola dynasty.",
        "keyTakeaways": ["Chola history", "Political intrigue"],
        "transcript": []
    },
    502: {
        "id": 502,
        "title": "Mookajjiya Kanasugalu",
        "author": "K. Shivarama Karanth",
        "language": "Kannada",
        "category": "History",
        "rating": 4.9,
        "cover": "https://c4.wallpaperflare.com/wallpaper/332/915/762/one-piece-roronoa-zoro-hd-wallpaper-preview.jpg",
        "audioSrc": "https://storage.googleapis.com/donotdeletechand1/kannada voices/book_502_Mookajjiya_Kanasugalu.mp3",
        "textSummary": "A novel that explores the evolution of human civilization and thought.",
        "keyTakeaways": ["Philosophy", "Evolution"],
        "transcript": []
    }
}

SERVER_AUTHOR_DATABASE = {
    "విశ్వనాథరెడ్డి": {
        "bio": "విశ్వనాథరెడ్డి గారు ప్రముఖ తెలుగు రచయిత మరియు కడప ప్రాంతపు వాస్తవిక కథలకు ప్రసిద్ధి చెందారు. ఆయన రచనలు రాయలసీమ మాండలికం మరియు సంస్కృతిని ప్రతిబింబిస్తాయి. గ్రామీణ జీవితం, ఫ్యాక్షన్ పోరాటాలు, మానవ సంబంధాలపై ఆయన చేసిన కృషి అపారమైనది.",
        "photo": "https://placehold.co/100x100/7c3aed/FFFFFF?text=VR",
    },
    "Cal Newport": {
        "bio": "Cal Newport is an American author and associate professor of computer science at Georgetown University. He is known for his non-fiction books on productivity and the intersection of technology and society, including 'Deep Work' and 'Digital Minimalism'. His work often explores how to thrive in an increasingly distracting world.",
        "photo": "https://placehold.co/100x100/A78BFA/FFFFFF?text=CN",
    },
    "Yuval Noah Harari": {
        "bio": "Yuval Noah Harari is an Israeli public intellectual, historian, and professor in the Department of History at the Hebrew University of Jerusalem. He is the author of the popular science bestsellers 'Sapiens: A Brief History of Humankind', 'Homo Deus: A Brief History of Tomorrow', and '21 Lessons for the 21st Century'. His writings examine free will, consciousness, intelligence, and happiness.",
        "photo": "https://placehold.co/100x100/8B5CF6/FFFFFF?text=YH",
    },
    "James Clear": {
        "bio": "James Clear is an author, speaker, and entrepreneur focused on habits, decision-making, and continuous improvement. He is best known for his book 'Atomic Habits', which has sold millions of copies worldwide and offers a proven framework for improving every day.",
        "photo": "https://placehold.co/100x100/6D28D9/FFFFFF?text=JC",
    },
    "Kalki Krishnamurthy": {
        "bio": "R. Krishnamurthy (1899–1954), better known by his pen name Kalki, was a Tamil writer, journalist, poet, critic and Indian independence activist. He is most famous for his historical novels, particularly 'Ponniyin Selvan', which is a masterpiece in Tamil literature.",
        "photo": "https://placehold.co/100x100/5B21B6/FFFFFF?text=KK",
    },
    "K. Shivarama Karanth": {
        "bio": "Kota Shivarama Karanth (1902–1997) was a prominent Kannada writer, novelist, playwright, and environmentalist. He was a recipient of the Jnanpith Award, India's highest literary honor. His works often reflected the cultural and social aspects of Karnataka.",
        "photo": "https://placehold.co/100x100/4C1D95/FFFFFF?text=KSK",
    },
}

# --- Frontend Serving Routes ---
@app.route('/')
def index():
    """Serves the login page as the default route."""
    return render_template('login.html')

@app.route('/login.html')
def login_page():
    """Explicit route for login page."""
    return render_template('login.html')

@app.route('/stories9.html')
def stories_page():
    """Explicit route for stories page."""
    return render_template('stories9.html')

# --- NEW API ENDPOINT for ALL Book Metadata (for initial display) ---
@app.route('/api/books-metadata', methods=['GET'])
def get_all_books_metadata():
    all_books_metadata = []
    for book_id, book_data in SERVER_BOOK_DATABASE.items():
        metadata = {
            "id": book_data["id"],
            "title": book_data["title"],
            "author": book_data["author"],
            "language": book_data["language"],
            "category": book_data["category"],
            "rating": book_data["rating"],
            "cover": book_data["cover"]
        }
        all_books_metadata.append(metadata)
    return jsonify(all_books_metadata)


# --- NEW API ENDPOINT for Specific Book Data (full details) ---
@app.route('/api/book/<int:book_id>', methods=['GET'])
def get_book_data(book_id):
    book_data = SERVER_BOOK_DATABASE.get(book_id)
    if not book_data:
        return jsonify({'error': 'Book not found'}), 404
    
    return jsonify(book_data)

# --- NEW API ENDPOINT for Author Data ---
@app.route('/api/author/<path:author_name>', methods=['GET'])
def get_author_data(author_name):
    decoded_author_name = unquote(author_name)
    author_info = SERVER_AUTHOR_DATABASE.get(decoded_author_name)
    if not author_info:
        return jsonify({'error': f'Author "{decoded_author_name}" not found'}), 404
    return jsonify(author_info)


# --- User Data Persistence Routes ---
@app.route('/user_data/<user_id>', methods=['GET'])
def load_user_data(user_id):
    if not gcs_bucket:
        logger.error("GCS bucket not initialized for load operation.")
        return jsonify({'error': 'Backend GCS service is not configured.'}), 500

    blob_name = f"{USER_DATA_FOLDER}/{user_id}.json"
    blob = gcs_bucket.blob(blob_name)
    logger.info(f"Attempting to load blob: {blob_name} for user {user_id}")

    try:
        if blob.exists():
            data = json.loads(blob.download_as_text())
            logger.info(f"SUCCESS: Loaded data for user {user_id} from GCS. Data length: {len(json.dumps(data))} bytes")
            return jsonify({
                'myLibrary': data.get('myLibrary', []),
                'userRatings': data.get('userRatings', {}),
                'listeningProgress': data.get('listeningProgress', {})
            })
        else:
            logger.info(f"INFO: No existing data for user {user_id} in GCS. Blob does not exist. Returning empty structure.")
            return jsonify({'myLibrary': [], 'userRatings': {}, 'listeningProgress': {}})
    except Exception as e:
        logger.error(f"Error during load of user data for {user_id}: {e}", exc_info=True)
        return jsonify({'error': f"Could not load user data: {e}"}), 500

@app.route('/user_data/<user_id>', methods=['POST'])
def save_user_data(user_id):
    if not gcs_bucket:
        logger.error("GCS bucket not initialized for save operation.")
        return jsonify({'error': 'Backend GCS service is not configured.'}), 500

    data = request.get_json()
    if not data:
        logger.error(f"No JSON data provided for save for user {user_id}.")
        return jsonify({'error': 'No data provided.'}), 400

    blob_name = f"{USER_DATA_FOLDER}/{user_id}.json"
    blob = gcs_bucket.blob(blob_name)
    logger.info(f"Attempting to save blob: {blob_name} for user {user_id}. Payload: {json.dumps(data)}")

    try:
        blob.upload_from_string(json.dumps(data), content_type='application/json')
        logger.info(f"SUCCESS: Saved data for user {user_id} to GCS.")
        return jsonify({'message': 'Data saved successfully.'})
    except Exception as e:
        logger.error(f"Error during save for {user_id} (Blob: {blob_name}): {e}", exc_info=True)
        return jsonify({'error': f"Could not save user data: {e}"}), 500

# --- Transcription Route ---
@app.route('/transcribe_audio', methods=['POST'])
def transcribe_audio():
    if not stt_client:
        return jsonify({'error': 'Backend STT service is not configured.'}), 500

    try:
        data = request.get_json()
        audio_url = data.get('audio_url')
        if not audio_url:
            return jsonify({'error': 'No audio_url provided.'}), 400

        gcs_uri = convert_to_gcs_uri(audio_url)
        if not gcs_uri:
            return jsonify({'error': f"Invalid public GCS URL provided or unable to convert: {audio_url}"}), 400

        logger.info(f"Transcribing audio from URI: {gcs_uri}")

        audio = speech.RecognitionAudio(uri=gcs_uri)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_word_time_offsets=True,
        )

        operation = stt_client.long_running_recognize(config=config, audio=audio)
        logger.info("Waiting for transcription to complete...")
        response = operation.result(timeout=300)

        transcript_result = []
        for result in response.results:
            alternative = result.alternatives[0]
            sentence = ""
            start_time = 0
            for word_info in alternative.words:
                if not sentence:
                    start_time = word_info.start_time.seconds + word_info.start_time.microseconds * 1e-6

                sentence += word_info.word + " "

                if word_info.word.endswith((".", "!", "?", "。")) or (word_info == alternative.words[-1] and sentence.strip()):
                    transcript_result.append({
                        'time': start_time,
                        'text': sentence.strip()
                    })
                    sentence = ""
            if sentence.strip():
                transcript_result.append({
                    'time': start_time,
                    'text': sentence.strip()
                })

        return jsonify({'transcript': transcript_result})

    except Exception as e:
        logger.error(f"Error during transcription: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# --- Razorpay Payment Routes ---
@app.route('/create-razorpay-order', methods=['POST'])
def create_razorpay_order():
    if not razorpay_client:
        logger.error("Razorpay client is not configured (likely API key issue).")
        return jsonify({'error': 'Razorpay client is not configured.'}), 500

    data = request.get_json()
    amount = data.get('amount')
    currency = data.get('currency', 'INR')
    receipt_id = data.get('receipt', f'receipt_{os.urandom(8).hex()}')

    if not amount or not isinstance(amount, int) or amount <= 0:
        logger.error(f"Invalid amount received for order creation: {amount}")
        return jsonify({'error': 'Invalid amount provided.'}), 400

    try:
        order_details = razorpay_client.order.create({
            'amount': amount,
            'currency': currency,
            'receipt': receipt_id,
            'payment_capture': '1'
        })
        logger.info(f"SUCCESS: Razorpay order created: {order_details['id']}")
        return jsonify(order_details)
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/verify-razorpay-payment', methods=['POST'])
def verify_razorpay_payment():
    if not razorpay_client:
        logger.error("Razorpay client is not configured for verification (likely API key issue).")
        return jsonify({'error': 'Razorpay client is not configured.'}), 500

    data = request.get_json()
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_signature = data.get('razorpay_signature')

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        logger.error("Missing payment verification data.")
        return jsonify({'error': 'Missing payment verification data.'}), 400

    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        })
        logger.info(f"SUCCESS: Razorpay payment verified for order: {razorpay_order_id}, payment: {razorpay_payment_id}")
        return jsonify({'message': 'Payment verification successful!'})
    except Exception as e:
        logger.error(f"Error verifying Razorpay payment: {e}", exc_info=True)
        return jsonify({'error': 'Payment verification failed.'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5500)