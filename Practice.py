from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import string
import re
import requests
from datetime import datetime, timedelta
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import logging
import json
from email.utils import parsedate_to_datetime
import nltk

# ---------------------------
# Initialization
# ---------------------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')
nltk.download('wordnet')

nltk.data.path.append("C:/Users/ADMIN/nltk_data")


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


def normalize(text):
    text = text.lower()
    text = re.sub(r'\b(\d+)\s*&\s*(\d+)\b', r'\1 and \2', text)

    text = text.replace('&', 'and')
    text = text.replace('&amp', 'and')
    text = text.replace('/', ' ')
    text = text.replace('\n', ' ')
    text = text.replace('-', ' ')

    # Replace known phrases with their normalized forms
    replacements = {
        "plant load factor": "plf",
        "plant availability factor": "paf",
        "auxiliary consumption": "aux consumption",
        "maximum power": "max power",
        "minimum power": "min power",
        "iex price": "iex price",
        "iex cost": "iex price",
        "iex rate": "iex price",
        "banked unit": "banking unit",
        "gen energy": "generated energy",
        "procurement price": "last_price",
        "procurement price for": "last_price",
        "energy generated": "generated energy",
        "energy generation": "generated energy",
        "cost generated": "generated cost",
    }
    for k, v in sorted(replacements.items(), key=lambda x: -len(x[0])):  # longest first
        text = text.replace(k, v)

    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = text.strip(string.punctuation)
    return text


# ---------------------------
# NLP Helpers
# ---------------------------
def preprocess(text):
    try:
        # Clean and normalize the text
        # Handle numeric "and" patterns like "3 and 4" → "3 and 4" (or optionally → "3 & 4")
        text = normalize(text)
        print("DEBUG cleaned text:", text)

        # Tokenize
        tokens = word_tokenize(text)
        print("DEBUG: Tokens =", tokens)
        cleaned = " ".join(tokens)

        # Filtered and lemmatized tokens
        processed_tokens = [
            lemmatizer.lemmatize(tok)
            for tok in tokens
            if tok not in stop_words and len(tok) > 1 and not tok.isnumeric()
        ]

        # Multi-word and single-word plant-related keywords
        plant_keywords = [
            "plf", "paf", "variable cost","aux consumption", "max power", "min power",
            "rated capacity", "type", "plant", "plant details", "auxiliary consumption", "technical minimum", "maximum power", "minimum power",
            "plant load factor", "plant availability factor", "aux usage", "auxiliary usage", "var cost"
        ]


        procurement_keywords =["banking unit", "banking contribution","banking","banked unit", "generated energy",
                               "procurement price", "generation energy", "energy generated", "energy generation", "demand banked",
                               "energy", "produce", "banked", "energy banked", "generated cost", "generation cost", "cost generated",
                               "cost generation"

        ]

        #combine all
        all_keywords = plant_keywords + procurement_keywords

        matched_keywords = set()
        for keyword in all_keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", text):
                matched_keywords.add(keyword)

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

            'mod': ['mod', 'mod price', 'dispatch price', 'grid', 'dispatch', 'moment', 'last_price', 'last price', 'moment', 'moment of dispatch',
                    'dispatch price', 'mod rate', ],

            'iex': ['iex', 'iex price', 'market price', 'exchange', 'market rate', 'exchange', 'iex cost', 'indian energy exchange', 'exchange'],

            'procurement': ['procurement', 'purchase', 'buy', 'bought', 'procure', 'procured', 'power purchase cost',
                           'procurement info', 'procurement price'],

            'cost per block': ['cost per block','cost rate', 'cost_per_block', 'block cost', 'rate per block', 'block rate'],

            'plant_info': [
                'plant', 'plant details', 'generation plant', 'power plant', 'generator info',
                'plant information', 'plant status', 'plant list', 'list of plants',
                'details of generation units', 'generating units', 'generation capacity',
                'power station', 'unit capacity', 'installed capacity', 'plant data',
                'plf', 'paf', 'variable cost', 'aux consumption', 'max power', 'var cost',
                'min power', 'rated capacity', 'type', 'auxiliary consumption', "maximum power",
                "minimum power", "technical minimum", "maximum power", "minimum power", "aux usage", "auxiliary usage"
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


        elif intent == "cost per block":
            try:
                ts = build_timestamp(date_str, time_obj)
                formatted_ts = ts.strftime("%Y-%m-%d %H:%M:%S")  # Adjusted format

                url = f"http://127.0.0.1:5000/procurement?start_date={formatted_ts}&price_cap=10"
                logger.debug(f"🔍 Procurement API URL: {url}")

                response = requests.get(url)
                logger.debug(f"🌐 API status: {response.status_code}")
                logger.debug(f"📦 Raw response JSON: {response.json()}")

                if response.status_code != 200:
                    return "Failed to fetch cost per block data."

                data = response.json()

                if not data or "Cost_Per_Block" not in data:
                    return "No data found for that time."

                cost = data["Cost_Per_Block"]

                return f"At {ts.time()} on {ts.date()}, the cost per block was ₹{cost}."

            except Exception as e:
                logger.error(f"Procurement API error: {e}")
                return "Error fetching cost per block data."



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


def fuzzy_match(a, b):
    return normalize(a) == normalize(b) or normalize(a) in normalize(b) or normalize(b) in normalize(a)


def handle_plant_info(date_str, time_obj, original_message):
    try:
        start_timestamp = f"{date_str} {time_obj.strftime('%H:%M:%S')}"
        plant_api_url = "http://127.0.0.1:5000/plant/"
        response = requests.get(plant_api_url)

        if response.status_code != 200:
            return "Failed to fetch plant details."

        data = response.json()
        all_plants = data.get("must_run", []) + data.get("other", [])

        if not all_plants:
            return "No plant data available."

        message = normalize(original_message)

        plant_field_map = {
            "plf": "PLF",
            "plant load factor": "PLF",
            "paf": "PAF",
            "plant availability factor": "PAF",
            "variable cost": "Variable_Cost",
            "aux consumption": "Aux_Consumption",
            "auxiliary consumption": "Aux_Consumption",
            "max power": "Max_Power",
            "min power": "Min_Power",
            "rated capacity": "Rated_Capacity",
            "type": "Type",
            "technical minimum": "Technical_Minimum",
            "aux usage": "Aux_Consumption",
            "auxiliary usage": "Aux_Consumption",
            "var cost": "Variable_Cost"
        }

        requested_field = None
        for k in plant_field_map:
            if k in message:
                requested_field = plant_field_map[k]
                break

        if not requested_field:
            return "Please specify whether you want PLF, PAF, variable cost, or some other technical parameter."

        # Try to match plant name from message
        match = re.search(r"(?:by|for|of)\s+([a-z0-9\s\-&/]+?)(?=\s+(?:on|at)\s+|[\?\.!]|$)", message, re.IGNORECASE)

        if match:
            print("🧠 Raw match group:", match.group(1))
            plant_query = normalize(match.group(1).replace('/', ' '))
            for plant in all_plants:
                plant_name = plant.get("name", "Unknown Plant")  # Changed from "plant_name" to "name"
                print(f"🔍 Comparing user input '{plant_query}' with plant '{plant_name}'")
                if fuzzy_match(normalize(plant_name), plant_query):
                    if requested_field not in plant:
                        return f"{requested_field.replace('_', ' ').capitalize()} not available for {plant_name} at {start_timestamp}."
                    value = plant[requested_field]
                    return f"{requested_field.replace('_', ' ').capitalize()} for {plant_name} at {start_timestamp}: {value}"
            return f"No plant found matching '{match.group(1)}'. Available plants: {[p.get('name', 'Unknown') for p in all_plants]}"
        else:
            return "Could not identify plant name in your query. Please try again specifying the plant name."

    except Exception as e:
        print(f"Error processing plant info: {str(e)}")
        return "An error occurred while processing your request."

def handle_procurement_info(original_message, date_str, time_obj):
    try:
        from urllib.parse import quote

        start_timestamp = f"{date_str} {time_obj.strftime('%H:%M:%S')}"
        url = f"http://127.0.0.1:5000/procurement?start_date={quote(start_timestamp)}&price_cap=10"
        response = requests.get(url)

        if response.status_code != 200:
            return "Failed to fetch procurement data."

        data = response.json()

        # Combine Must_Run and Remaining_Plants if they exist
        all_plants = data.get("Must_Run", []) + data.get("Remaining_Plants", [])

        if not all_plants:
            return "No procurement data available for the given time."

        # Add cost_generated (Generated_Cost) field
        for plant in all_plants:
            vc = plant.get("Variable_Cost", 0.0)
            gen = plant.get("generated_energy", 0.0)
            plant["Generated_Cost"] = round(vc * gen, 2)

        message = normalize(original_message)

        field_map = {
            "banking unit": "Banking_Unit",
            "banked unit": "Banking_Unit",
            "generated energy": "generated_energy",
            "banking": "Banking_unit",
            "banking contribution": "Banking_unit",
            "energy": "Generated_Energy",
            "energy generated": "generated_Energy",
            "energy generation": "generated_Energy",
            "banked contribution": "Banking_unit",
            "banked": "Banking_unit",
            "demand banked": "Banking_unit",
            "energy banked": "Banking_unit",
            "generated cost": "Generated_Cost",
            "generation cost": "Generated_Cost",
            "cost generated": "Generated_Cost",
            "cost generation": "Generated_Cost",
        }

        requested_field = None
        for k in field_map:
            if k in message:
                requested_field = field_map[k]
                break

        if not requested_field:
            return "Please specify whether you want IEX cost, generated energy, banking unit or cost generated"

        if requested_field in data:
            return f"{requested_field.replace('_', ' ').capitalize()} at {start_timestamp}: {data[requested_field]}"

        match = re.search(r"(?:by|for|of)\s+([a-z0-9\s\-&/]+?)(?=\s+(?:on|at)\s+|[\?\.!]|$)", message)

        if match:
            print("🧠 Raw match group:", match.group(1))
            plant_query = normalize(match.group(1).replace('/', ' '))
            for plant in all_plants:
                if fuzzy_match(normalize(plant["plant_name"]), plant_query):
                    if requested_field not in plant:
                        return f"{requested_field.replace('_', ' ').capitalize()} not available for {plant['plant_name']} at {start_timestamp}."

                    value = plant[requested_field]
                    return f"{requested_field.replace('_', ' ').capitalize()} for {plant['plant_name']} at {start_timestamp}: {value}"

            return f"No plant found matching '{match.group(1)}'."

        else:
            lines = []
            for plant in all_plants:
                value = plant.get(requested_field, 'N/A')
                lines.append(f"{plant['plant_name']} ({requested_field.replace('_', ' ')}): {value}")
            return f"{requested_field.replace('_', ' ').capitalize()} values for all plants at {start_timestamp}:\n" + "\n".join(lines)

    except Exception as e:
        logger.error(f"Procurement API error: {e}")
        return "Error fetching procurement data."


# ---------------------------
# Chat Interface
# ---------------------------
def get_response(user_input):
    static = match_static_qa(user_input)
    if static:
        return static

    toks, matched_keywords = preprocess(user_input)
    print("🔍 Tokens:", toks)
    print("✅ Matched Keywords:", matched_keywords)

    # Extract date and time once
    date_str = extract_date(user_input)
    time_obj = extract_time(user_input)

    # PLANT INFO check
    if any(k in matched_keywords for k in [
        'plf', 'paf', 'variable cost', 'aux consumption', 'max power', 'min power',
        'rated capacity', 'technical minimum', 'type', 'maximum power', 'minimum power',
        'auxiliary consumption', 'plant load factor', 'plant availability factor',
        'aux usage', 'auxiliary usage', 'var cost'
    ]):
        if not date_str or not time_obj:
            return "Please specify both date and time for the plant information."
        return handle_plant_info(date_str, time_obj, user_input)

    # PROCUREMENT check
    if any(k in matched_keywords for k in [
        'banking', 'banking unit','banked', 'energy generated','banked unit','banking contribution',
        'generated energy', 'procurement price', 'energy', 'iex cost', 'demand banked',
        'cost generated', 'generated cost', 'generation cost', 'generated cost'
    ]):
        print("📅 Extracted date:", date_str)
        print("⏰ Extracted time:", time_obj)

        if not date_str or not time_obj:
            return "Sorry, I couldn't understand your request."
        return handle_procurement_info(user_input, date_str, time_obj)

    # FALLBACK for other intents like demand, iex, mod
    if not time_obj:
        return "Sorry, I couldn't understand your request."

    intent = get_intent(toks, user_input)
    if not intent:
        return "Sorry, I couldn't understand your request."

    if intent == "procurement":
        return handle_procurement_info(user_input, date_str, time_obj)

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
