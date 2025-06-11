from flask import Flask, request, jsonify, make_response
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
    "what is the definition of moment of dispatch price": "The Moment of Dispatch (MOD) price refers to the cost of electricity at a specific 15-minute time block when it is dispatched to meet demand. It is used in electricity markets and grid operations to determine the economic value or cost of delivering electricity at a given moment, based on real-time supply and demand conditions.",
    "what is the indian energy exchange price definition": "The Indian Energy Exchange (IEX) price refers to the market-determined clearing price of electricity traded on the Indian Energy Exchange for specific time blocks during the day.",
    "what is the definition of mod": "MOD (Moment of Dispatch) refers to the specific point in time when electricity is actually dispatched (sent out) from the generation source to meet the demand on the grid. It is a concept used in power system operations to represent real-time grid balancing based on forecasted and actual demand.",
    "what is iex": "Indian Energy Exchange (IEX) is India’s premier electricity trading platform, where buyers and sellers of electricity participate in transparent, auction-based energy trading across various timeframes such as day-ahead, real-time, and term-ahead markets."
}

def match_static_qa(user_input):
    cleaned = re.sub(r'[^\w\s]', '', user_input.lower().strip())

    keyword_map = {
        "moment of dispatch price": static_qa["what is the definition of moment of dispatch price"],
        "indian energy exchange price": static_qa["what is the indian energy exchange price definition"],
        "definition of mod": static_qa["what is the definition of mod"],
        "what is iex": static_qa["what is iex"],
        "mod price": static_qa["what is the definition of moment of dispatch price"],
        "moment of dispatch rate": static_qa["what is the definition of moment of dispatch price"],
        "mod rate": static_qa["what is the definition of moment of dispatch price"],
        "iex price": static_qa["what is the indian energy exchange price definition"],
        "iex rate": static_qa["what is the indian energy exchange price definition"],
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




    }

    for keyword, response in keyword_map.items():
        if keyword in cleaned:
            return response

    return None


# ---------------------------
# Database Connection
# ---------------------------
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="powerplus_pool",
        pool_size=5,
        host="localhost",
        user="root",
        password="Aradhya03101998*",
        database="guvnl_db",
        autocommit=True
    )
    logger.info("Database connection pool created successfully")
except mysql.connector.Error as err:
    logger.error(f"Failed to create database connection pool: {err}")
    raise

def get_db_connection():
    return db_pool.get_connection()

# ---------------------------
# NLP Helpers
# ---------------------------
def preprocess(text):
    try:
        text = re.sub(r'[^\w\s]', ' ', text.lower().strip())
        tokens = word_tokenize(text)
        return [lemmatizer.lemmatize(token) for token in tokens if token not in stop_words and len(token) > 1 and not token.isnumeric()]
    except Exception as e:
        logger.error(f"Preprocessing error: {e}")
        return []

def extract_date(text):
    try:
        match = re.search(r'\b(202\d-\d{2}-\d{2})\b', text)
        return match.group(1) if match else datetime.now().strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Date extraction error: {e}")
        return datetime.now().strftime('%Y-%m-%d')

def extract_time(text):
    try:
        match = re.search(r'\b(\d{1,2}:\d{2})\b', text)
        return datetime.strptime(match.group(1), '%H:%M').time() if match else None
    except Exception as e:
        logger.error(f"Time extraction error: {e}")
        return None

def build_timestamp(date_str, time_obj):
    return datetime.combine(datetime.strptime(date_str, "%Y-%m-%d").date(), time_obj)

def get_intent(tokens, raw_text):
    try:
        intent_keywords = {
            'demand': ['demand', 'consumption', 'average', 'load', 'forecast', 'electricity'],
            'mod': ['mod', 'mod price', 'dispatch price', 'grid', 'dispatch', 'moment'],
            'iex': ['iex', 'iex price', 'market price', 'exchange', 'market rate', 'exchange']
        }

        lower_text = raw_text.lower()
        for intent, keywords in intent_keywords.items():
            if any(k in lower_text for k in keywords):
                return intent
        for intent, keywords in intent_keywords.items():
            if any(token in tokens for token in keywords):
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
        timestamp = build_timestamp(date_str, time_obj)

        if intent == "mod":
            cursor.execute("SELECT last_price FROM demand_output WHERE timestamp = %s", (timestamp,))
            row = cursor.fetchone()
            return f"The MOD price for {timestamp} is ₹{row['last_price']}" if row and row['last_price'] else "No MOD price data found for that timestamp."

        elif intent == "iex":
            cursor.execute("SELECT Pred FROM price WHERE timestamp = %s", (timestamp,))
            row = cursor.fetchone()
            return f"The IEX price for {timestamp} is ₹{row['Pred']}" if row and row['Pred'] else "No IEX price data found for that timestamp."

        elif intent == "demand":
            target_date = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
            target_timestamp = build_timestamp(target_date.strftime("%Y-%m-%d"), time_obj)
            cursor.execute(
                """SELECT AVG(demand_pred) as avg_demand FROM demand_output
                   WHERE TIME(timeStamp) = %s AND DATE(timeStamp) = %s""",
                (target_timestamp.time(), target_date.date())
            )
            row = cursor.fetchone()
            return f"The average demand for {target_timestamp.time()} on {target_date.date()} is {round(row['avg_demand'], 2)} kWh" if row and row['avg_demand'] else "No demand data found for that time."

        return "Sorry, I don't have data for that request."

    except Exception as e:
        logger.error("DB Error: %s", str(e))
        traceback.print_exc()
        return f"Database error: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

def get_response(user_input):
    static_answer = match_static_qa(user_input)
    if static_answer:
        return static_answer

    tokens = preprocess(user_input)
    date_str = extract_date(user_input)
    time_obj = extract_time(user_input)

    if not time_obj:
        return "Please provide a valid time in HH:MM format."

    intent = get_intent(tokens, user_input)
    if not intent:
        return "Sorry, I couldn't understand your request."

    return generate_response(intent, date_str, time_obj)

# ---------------------------
# Flask App Routes
# ---------------------------
app = Flask("PowerPlus-NLP")

@app.route("/get", methods=["GET"])
def handle_chat():
    try:
        user_input = request.args.get("msg", "").strip()
        if not user_input:
            return jsonify({"error": "Empty request"}), 400

        logger.info(f"Received request: {user_input}")
        response = get_response(user_input)
        resp = make_response(json.dumps({"response": response}, ensure_ascii=False))
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        return resp

    except Exception as e:
        logger.error(f"Error in handle_chat: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
