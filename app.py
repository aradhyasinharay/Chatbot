import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import nltk
import string
import re
import mysql.connector
from mysql.connector import pooling
from datetime import datetime, timedelta
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import logging
import traceback
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ---------------------------
# Initialization
# ---------------------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

nltk.download('punkt', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('stopwords', quiet=True)

lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

# ---------------------------
# Static Knowledge Base
# ---------------------------
static_qa = {
    "what is the definition of moment of dispatch price":
        "The Moment of Dispatch (MOD) price refers to the cost of electricity at a specific 15-minute time block when it is dispatched to meet demand. It is used in electricity markets and grid operations to determine the economic value or cost of delivering electricity at a given moment, based on real-time supply and demand conditions.",
    "what is the indian energy exchange price definition":
        "The Indian Energy Exchange (IEX) price refers to the market-determined clearing price of electricity traded on the Indian Energy Exchange for specific time blocks during the day.",
    "what is the definition of mod":
        "MOD (Moment of Dispatch) refers to the specific point in time when electricity is actually dispatched (sent out) from the generation source to meet the demand on the grid. It is a concept used in power system operations to represent real-time grid balancing based on forecasted and actual demand.",
    "what is iex":
        "Indian Energy Exchange (IEX) is India’s premier electricity trading platform, where buyers and sellers of electricity participate in transparent, auction-based energy trading across various timeframes such as day-ahead, real-time, and term-ahead markets."
}

# ---------------------------
# Database Connection (using environment variables)
# ---------------------------
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', '')
DB_NAME = os.getenv('DB_NAME', 'guvnl_dev')
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', 5))

try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="powerplus_pool",
        pool_size=DB_POOL_SIZE,
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        autocommit=True
    )
    logger.info("Database connection pool created successfully")
except mysql.connector.Error as err:
    logger.error(f"Failed to create database connection pool: {err}")
    raise


def get_db_connection():
    return db_pool.get_connection()


# ---------------------------
# NLP Helpers and Logic...
# (Unchanged from your original code)
# ---------------------------
# match_static_qa, preprocess, extract_date, extract_time,
# build_timestamp, get_intent, generate_response, get_response

# ---------------------------
# Flask App
# ---------------------------
app = Flask("PowerPlus-NLP")
CORS(app)


@app.route("/get", methods=["GET"])
def handle_chat():
    try:
        user_input = request.args.get("msg", "").strip()
        if not user_input:
            return jsonify({"error": "Empty request"}), 400

        logger.info(f"Received request: {user_input}")
        response_text = get_response(user_input)
        resp = make_response(json.dumps({"response": response_text}, ensure_ascii=False))
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp

    except Exception as e:
        logger.error(f"Error in handle_chat: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv('PORT', 5050)), debug=True)
