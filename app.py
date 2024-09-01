from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
from pymongo import DESCENDING, MongoClient, ReturnDocument
from dotenv import load_dotenv
import os,re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1

app = Flask(__name__)

# Allow requests from specific origins
CORS(app, origins=["https://chess-main.vercel.app","https://chessdemo-alpha.vercel.app","https://chessdemo-l3qrzgj5q-ramyas-projects-4cb2348e.vercel.app","https://chess-main-git-main-ramyas-projects-4cb2348e.vercel.app","http://localhost:3000"])

load_dotenv()

# Get the MongoDB URI from the environment variable
mongo_uri = os.getenv('MONGO_URI')

# MongoDB setup
client = MongoClient(mongo_uri)
db = client.chessclub
users_collection = db.users

@app.route('/')
def home():
    return "Hello, Flask on Vercel!"

def time_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
 
@app.route('/signup', methods=['POST'])
def signup():
    user_data = request.get_json()
    if user_data:
        email = user_data.get('email')
        level = user_data.get('level')
        contact_number = user_data.get('contactNumber')
        
        # Check if user already exists
        existing_user = users_collection.find_one({'email': email, 'contactNumber': contact_number,'level':level})
        if existing_user:
            return jsonify({'error': 'User already exists. Please login.'}), 400
        
        # Add new user data
        users_collection.insert_one(user_data)
        return jsonify({'success': True}), 201
    else:
        return jsonify({'error': 'Invalid data format.'}), 400

@app.route('/signin', methods=['POST'])
def login():
    login_data = request.get_json()
    email = login_data.get('email') 
    
    # Retrieve the user from the database
    user = users_collection.find_one({'email': email})
    print(user)
    
    
    if user:
        name = user.get('name')
        return jsonify({'success': True, 'message': 'Login successfull','name': name}), 200
    return jsonify({'success': False,'message': 'Email and Mobile Number is not registered'}), 200
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

