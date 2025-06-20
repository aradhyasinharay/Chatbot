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
    "Hi": "Hello! How can I assist you today?",
    "Explain about yourself": "Hi I am Aradhya, your virtual assistant. I can help you with information about electricity demand, MOD prices, IEX rate. Just ask me anything related to power and energy!",
    "what is the definition of moment of dispatch price":
        "The Moment of Dispatch (MOD) price refers to the cost of electricity at a specific 15-minute time block when it is dispatched to meet demand. It is used in electricity markets and grid operations to determine the economic value or cost of delivering electricity at a given moment, based on real-time supply and demand conditions.",
    "what is the indian energy exchange price definition":
        "The Indian Energy Exchange (IEX) price refers to the market-determined clearing price of electricity traded on the Indian Energy Exchange for specific time blocks during the day.",
    "what is the definition of mod":
        "MOD (Moment of Dispatch) refers to the specific point in time when electricity is actually dispatched (sent out) from the generation source to meet the demand on the grid. It is a concept used in power system operations to represent real-time grid balancing based on forecasted and actual demand.",
    "what is iex":
        "Indian Energy Exchange (IEX) is India’s premier electricity trading platform, where buyers and sellers of electricity participate in transparent, auction-based energy trading across various timeframes such as day-ahead, real-time, and term-ahead markets.",
    "error": "Sorry, I am unable to understand your requirement.",
}


def match_static_qa(user_input):
    cleaned = re.sub(r'[^\w\s]', '', user_input.lower().strip())
    keyword_map = {
        "fuck you": static_qa["error"],
        "hi": static_qa["Hi"],
        "hello": static_qa["Hi"],
        "hey": static_qa["Hi"],
        "love you": static_qa["error"],
        "explain about yourself": static_qa["Explain about yourself"],
        "tell me about yourself": static_qa["Explain about yourself"],
        "definition of mod": static_qa["what is the definition of mod"],
        "what is iex": static_qa["what is iex"],
        "what is mod": static_qa["what is the definition of mod"],
        "definition of iex": static_qa["what is iex"],
        "what is moment of dispatch price": static_qa["what is the definition of moment of dispatch price"],
        "what is moment of dispatch rate": static_qa["what is the definition of moment of dispatch price"],
        "what is indian energy exchange price": static_qa["what is the indian energy exchange price definition"],
        "what is indian energy exchange rate": static_qa["what is the indian energy exchange price definition"],
        "what is iex price": static_qa["what is the indian energy exchange price definition"],
        "what is mod price": static_qa["what is the definition of moment of dispatch price"],
        "what is mod rate": static_qa["what is the definition of moment of dispatch price"],
        "what is iex rate": static_qa["what is the indian energy exchange price definition"],
        "what is the definition of moment of dispatch price": static_qa[
            "what is the definition of moment of dispatch price"],
        "what is the definition of moment of dispatch rate": static_qa[
            "what is the definition of moment of dispatch price"],
        "what is the definition of indian energy exchange price": static_qa[
            "what is the indian energy exchange price definition"],
        "what is the definition of indian energy exchange rate": static_qa[
            "what is the indian energy exchange price definition"],
        "what is the definition of IEX rate": static_qa["what is the indian energy exchange price definition"],
        "what is the definition of IEX price": static_qa["what is the indian energy exchange price definition"],
        "what is the definition of MOD price": static_qa["what is the definition of moment of dispatch price"],
        "what is the definition of MOD rate": static_qa["what is the definition of moment of dispatch price"],
        "what is indian energy exchange price definition": static_qa[
            "what is the indian energy exchange price definition"],
        "what is indian energy exchange rate definition": static_qa[
            "what is the indian energy exchange price definition"],
        "what is moment of dispatch price definition": static_qa["what is the definition of moment of dispatch price"],
        "what is moment of dispatch rate definition": static_qa["what is the definition of moment of dispatch price"],
        "what is the definition of mod": static_qa["what is the definition of mod"],
        "definition of moment of dispatch": static_qa["what is the definition of mod"],
        "what is the definition of moment of dispatch": static_qa["what is the definition of mod"],
        "what is the definition iex": static_qa["what is iex"],
        "what is the definition indian energy exchange": static_qa["what is iex"],
        "what is indian energy exchange": static_qa["what is iex"],
    }
    # Sort by longest keyword first
    for keyword, resp in sorted(keyword_map.items(), key=lambda x: -len(x[0])):
        if keyword in cleaned:
            return resp
    return None


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


def get_db_connection():
    return db_pool.get_connection()


# ---------------------------
# NLP Helpers
# ---------------------------
def preprocess(text):
    try:
        text = re.sub(r'[^\w\s]', ' ', text.lower().strip())
        tokens = word_tokenize(text)
        return [
            lemmatizer.lemmatize(tok)
            for tok in tokens
            if tok not in stop_words and len(tok) > 1 and not tok.isnumeric()
        ]
    except Exception as e:
        logger.error(f"Preprocessing error: {e}")
        return []


def extract_date(text):
    try:
        m = re.search(r'\b(202\d-\d{2}-\d{2})\b', text)
        return m.group(1) if m else datetime.now().strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Date extraction error: {e}")
        return datetime.now().strftime('%Y-%m-%d')


def extract_time(text):
    try:
        m = re.search(r'\b(\d{1,2}:\d{2})\b', text)
        return datetime.strptime(m.group(1), '%H:%M').time() if m else None
    except Exception as e:
        logger.error(f"Time extraction error: {e}")
        return None


def build_timestamp(date_str, time_obj):
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return datetime.combine(d, time_obj)


def get_intent(tokens, raw_text):
    try:
        intents = {
            'demand': ['demand', 'consumption', 'average', 'load', 'forecast', 'electricity'],
            'mod': ['mod', 'dispatch', 'moment'],
            'iex': ['iex', 'market', 'exchange']
        }
        low = raw_text.lower()
        for intent, kws in intents.items():
            if any(k in low for k in kws):
                return intent
        for intent, kws in intents.items():
            if any(tok in toks for toks in [tokens] for tok in kws):
                return intent
        return None
    except Exception as e:
        logger.error(f"Intent detection error: {e}")
        return None


# ---------------------------
# Query Handling
# ---------------------------
def generate_response(intent, date_str, time_obj):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        ts = build_timestamp(date_str, time_obj)

        if intent == "mod":
            cursor.execute("SELECT last_price FROM demand_output WHERE timestamp = %s", (ts,))
            row = cursor.fetchone()
            return (f"The MOD price for {ts} is ₹{row['last_price']}"
                    if row and row['last_price'] else
                    "No MOD price data found for that timestamp.")

        elif intent == "iex":
            cursor.execute("SELECT Pred FROM price WHERE timestamp = %s", (ts,))
            row = cursor.fetchone()
            return (f"The IEX price for {ts} is ₹{row['Pred']}"
                    if row and row['Pred'] else
                    "No IEX price data found for that timestamp.")

        elif intent == "demand":
            next_date = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
            target_ts = build_timestamp(next_date.strftime("%Y-%m-%d"), time_obj)
            cursor.execute(
                "SELECT AVG(demand_pred) as avg_demand FROM demand_output "
                "WHERE TIME(timestamp) = %s AND DATE(timestamp) = %s",
                (target_ts.time(), next_date.date())
            )
            row = cursor.fetchone()
            return (
                f"The average demand for {target_ts.time()} on {next_date.date()} is {round(row['avg_demand'], 2)} kWh"
                if row and row['avg_demand'] else
                "No demand data found for that time.")

        return "Sorry, I don't have data for that request."

    except Exception as e:
        logger.error(f"DB Error: {e}", exc_info=True)
        return f"Database error: {e}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def get_response(user_input):
    # 1) static QA
    static = match_static_qa(user_input)
    if static:
        return static

    # 2) dynamic
    toks = preprocess(user_input)
    date_str = extract_date(user_input)
    time_obj = extract_time(user_input)
    if not time_obj:
        return "Please provide a valid time in HH:MM format."

    intent = get_intent(toks, user_input)
    if not intent:
        return "Sorry, I couldn't understand your request."

    return generate_response(intent, date_str, time_obj)


# ---------------------------
# Flask App Routes
# ---------------------------
app = Flask("PowerPlus-NLP")
CORS(app)  # Enable CORS on all routes


@app.route("/get", methods=["GET"])
def handle_chat():
    try:
        user_input = request.args.get("msg", "").strip()
        if not user_input:
            return jsonify({"error": "Empty request"}), 400

        logger.info(f"Received request: {user_input}")
        resp_text = get_response(user_input)
        resp = make_response(json.dumps({"response": resp_text}, ensure_ascii=False))
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp

    except Exception as e:
        logger.error(f"Error in handle_chat: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
