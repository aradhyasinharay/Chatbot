import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import nltk
import string
import re
import requests
from datetime import datetime, timedelta
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import logging
import traceback
import json
from email.utils import parsedate_to_datetime

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
    "what is the definition of moment of dispatch price": "The Moment of Dispatch (MOD) price refers to the cost of electricity at a specific 15-minute time block when it is dispatched to meet demand. It is used in electricity markets and grid operations to determine the economic value or cost of delivering electricity at a given moment, based on real-time supply and demand conditions.",
    "what is the indian energy exchange price definition": "The Indian Energy Exchange (IEX) price refers to the market-determined clearing price of electricity traded on the Indian Energy Exchange for specific time blocks during the day.",
    "what is the definition of mod": "MOD (Moment of Dispatch) refers to the specific point in time when electricity is actually dispatched (sent out) from the generation source to meet the demand on the grid.",
    "what is iex": "Indian Energy Exchange (IEX) is India’s premier electricity trading platform...",
    "error": "Sorry, I am unable to understand your requirement."
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
    for keyword, resp in sorted(keyword_map.items(), key=lambda x: -len(x[0])):
        if keyword in cleaned:
            return resp
    return None

# ---------------------------
# NLP Helpers
# ---------------------------
def preprocess(text):
    try:
        # Clean and normalize the text
        text = re.sub(r'[^\w\s]', ' ', text.lower().strip())

        # Tokenize
        tokens = word_tokenize(text)

        # Define a set of keywords relevant to plant details
        plant_keywords = {"plf", "paf", "variable", "cost", "aux", "consumption", "max", "min", "power", "rated", "capacity", "type"}

        # Filtered and lemmatized tokens
        processed_tokens = [
            lemmatizer.lemmatize(tok)
            for tok in tokens
            if tok not in stop_words and len(tok) > 1 and not tok.isnumeric()
        ]

        # Check if any of the tokens match known keywords for intent detection
        matched_keywords = set(processed_tokens).intersection(plant_keywords)

        return processed_tokens, matched_keywords

    except Exception as e:
        logger.error(f"Preprocessing error: {e}")
        return [], set()


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
            'mod': ['mod', 'mod price', 'dispatch price', 'grid', 'dispatch', 'moment', 'last_price', 'last price'],
            'iex': ['iex', 'iex price', 'market price', 'exchange', 'market rate', 'exchange'],
            'procurement': ['procurement', 'purchase', 'buy', 'bought', 'procure', 'cost per block', 'cost_per_block', 'procured', 'power purchase cost',
                            'block cost', 'procurement info', 'procurement price'],
            'procurement_range': [
                'procurement range', 'purchase range', 'buy range', 'procurement data between',
                'procurement data from', 'procurement data for', 'procurement during',
                'procure from', 'procurement between', 'procurement from', 'procurement in range',
                'procurement records between', 'procurement records from', 'procurement for range',
                'buying pattern', 'purchased between', 'bought from', 'buy data range'
            ],
            'plant_info': [
                'plant', 'plant details', 'generation plant', 'power plant', 'generator info',
                'plant information', 'plant status', 'plant list', 'list of plants',
                'details of generation units', 'generating units', 'generation capacity',
                'power station', 'unit capacity', 'installed capacity', 'plant data',
                'plf', 'paf', 'variable cost', 'aux consumption', 'max power',
                'min power', 'rated capacity', 'type'
            ]
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
# Dynamic Response Handler (API-based)
# ---------------------------
def generate_response(intent, date_str, time_obj, original_message=""):

    try:
        ts = build_timestamp(date_str, time_obj)
        iso_ts = ts.isoformat()

        if intent == "mod":
            try:
                # Build MOD API URL
                start_str = ts.strftime("%Y-%m-%d %H:%M:%S")
                end_str = (ts + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
                mod_api_url = f"http://127.0.0.1:5000/procurement/range?start={start_str}&end={end_str}"
                response = requests.get(mod_api_url)

                logger.debug(f"MOD API status: {response.status_code}")
                logger.debug(f"MOD API response text: {response.text}")

                if response.status_code != 200:
                    return "Failed to fetch MOD price data."

                result = response.json()
                data = result.get("data", [])

                matched = None
                for item in data:
                    try:
                        api_ts = parsedate_to_datetime(item["timestamp"]).replace(tzinfo=None)
                        logger.debug(f"Comparing MOD timestamp {api_ts} with {ts}")
                        if api_ts == ts:
                            matched = item
                            break
                    except Exception as e:
                        logger.warning(f"Skipping item due to timestamp error: {e}")

                if matched:
                    return f"The MOD price at {ts.time()} on {ts.date()} is ₹{matched['last_price']} per unit."
                else:
                    return "No MOD data found for that time."

            except Exception as e:
                logger.error(f"MOD API error: {e}")
                return "Error fetching MOD data."


        elif intent == "procurement":
            try:
                ts = build_timestamp(date_str, time_obj)
                formatted_ts = ts.strftime("%Y-%m-%d %H:%M:%S")  # Adjusted format

                url = f"http://127.0.0.1:5000/procurement?start_date={formatted_ts}&price_cap=10"
                logger.debug(f"🔍 Procurement API URL: {url}")

                response = requests.get(url)
                logger.debug(f"🌐 API status: {response.status_code}")
                logger.debug(f"📦 Raw response JSON: {response.json()}")

                if response.status_code != 200:
                    return "Failed to fetch procurement data."

                data = response.json()

                if not data or "Cost_Per_Block" not in data:
                    return "No procurement data found for that time."

                cost = data["Cost_Per_Block"]

                return f"At {ts.time()} on {ts.date()}, the procurement cost per block was ₹{cost}."

            except Exception as e:
                logger.error(f"Procurement API error: {e}")
                return "Error fetching procurement data."



        elif intent == "iex":
            try:
                iex_api_url = f"http://localhost:5000/iex/range?start={ts.isoformat()}&end={(ts + timedelta(minutes=1)).isoformat()}"
                response = requests.get(iex_api_url)

                logger.debug(f"IEX API status: {response.status_code}")
                logger.debug(f"IEX API response text: {response.text}")

                if response.status_code != 200:
                    return "Failed to fetch IEX price data."

                result = response.json()
                data = result.get("data", [])

                logger.debug(f"Looking for ISO timestamp: {iso_ts}")

                matched = None
                for item in data:
                    try:
                        api_ts = parsedate_to_datetime(item["TimeStamp"]).replace(tzinfo=None)
                        logger.debug(f"Comparing API timestamp {api_ts} with target {ts}")
                        if api_ts == ts:
                            matched = item
                            break
                    except Exception as e:
                        logger.warning(f"Skipping item due to timestamp error: {e}")

                if matched:
                    return f"The IEX market rate at {ts.time()} on {ts.date()} is ₹{matched['predicted']} per unit."
                else:
                    return "No IEX data found for that time."

            except Exception as e:
                logger.error(f"IEX API error: {e}")
                return "Error fetching IEX data."


        elif intent == "plant_info":
            try:
                plant_api_url = "http://127.0.0.1:5000/plant/"
                response = requests.get(plant_api_url)

                if response.status_code != 200:
                    return "Failed to fetch plant details."

                data = response.json().get("must_run", [])
                if not data:
                    return "No plant data available."

                user_msg_lower = original_message.lower()

                # Mapping keywords to plant data fields
                plant_fields = {
                    "plf": "PLF",
                    "paf": "PAF",
                    "variable cost": "Variable_Cost",
                    "aux consumption": "Aux_Consumption",
                    "max power": "Max_Power",
                    "min power": "Min_Power",
                    "rated capacity": "Rated_Capacity",
                    "type": "Type"
                }

                # Try to match field and optionally extract plant name
                for keyword, field_key in plant_fields.items():
                    if keyword in user_msg_lower:
                        # Try to extract specific plant name (e.g., "plf for Waste to Energy")
                        match = re.search(rf"{keyword} for (.+)", user_msg_lower)
                        if match:
                            plant_query = match.group(1).strip()
                            for plant in data:
                                if plant_query.lower() in plant["name"].lower():
                                    return f"{field_key} for {plant['name']}: {plant.get(field_key, 'N/A')}"
                            return f"No plant found matching '{plant_query}'."
                        else:
                            # If no plant name, list for all
                            def format_field(p):
                                return f"{p['name']} ({field_key}): {p.get(field_key, 'N/A')}"

                            return f"{field_key} values for Must Run plants:\n" + "\n".join(
                                [format_field(p) for p in data])

                # If no field matched
                return json.dumps(data, indent=2)

            except Exception as e:
                logger.error(f"Plant API error: {e}")
                return "Error fetching plant data."


        elif intent == "demand":
            try:
                target_ts = build_timestamp(
                    (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
                    time_obj
                )
                start_ts = target_ts.isoformat()
                end_ts = (target_ts + timedelta(minutes=1)).isoformat()
                demand_api_url = f"http://localhost:5000/demand/range?start={start_ts}&end={end_ts}"
                response = requests.get(demand_api_url)
                if response.status_code != 200:
                    return "Failed to fetch demand data."
                data = response.json().get("data", [])
                if not data:
                    return "No demand data found for that time."
                avg_demand = sum(row["predicted"] for row in data) / len(data)
                return f"The average demand for {target_ts.time()} on {target_ts.date()} is {round(avg_demand, 2)} kWh"
            except Exception as e:
                logger.error(f"Demand API error: {e}")
                return "Error fetching demand data."

        return "Sorry, I don't have data for that request."

    except Exception as e:
        logger.error(f"generate_response error: {e}")
        return "Internal error while processing the request."

# ---------------------------
# Chat Interface
# ---------------------------
def get_response(user_input):
    static = match_static_qa(user_input)
    if static:
        return static

    toks = preprocess(user_input)
    date_str = extract_date(user_input)
    time_obj = extract_time(user_input)
    if not time_obj:
        return "Sorry, I couldn't understand your request."

    intent = get_intent(toks, user_input)
    if not intent:
        return "Sorry, I couldn't understand your request."

    return generate_response(intent, date_str, time_obj)

# ---------------------------
# Flask App
# ---------------------------
app = Flask("Aradhya")
CORS(app)

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

# ---------------------------
# Flask App Runner
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
