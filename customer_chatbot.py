from flask import Flask, request, jsonify, render_template_string
from nlp_utils import classify_intent

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return render_template_string("""
        <h2>Customer Chatbot Test</h2>
        <form method="POST" action="/chat">
            <label>Enter your message:</label><br>
            <input type="text" name="message" size="60">
            <br><br>
            <input type="submit" value="Send">
        </form>
    """)

@app.route("/chat", methods=["POST"])
def chat():
    # JSON request (API)
    if request.is_json:
        data = request.get_json()
        user_input = data.get("message", "")
    else:
        # Form request (from browser)
        user_input = request.form.get("message", "")

    intent = classify_intent(user_input)
    response = generate_response(intent)

    return jsonify({
        "intent": intent,
        "response": response
    })

def generate_response(intent):
    if intent == "power_theft":
        return "Thank you for reporting power theft. A ticket has been raised and our team will look into it. Please share your customer ID. "
    elif intent == "load_change":
        return "Please provide your customer ID to proceed with load change request."
    elif intent == "new_connection":
        return "To apply for a new connection, please provide your address and customer ID."
    elif intent == "power_outage":
        return "Sorry for the inconvenience. Please share your area PIN code so we can check the outage."
    else:
        return "Sorry, I couldn't understand your request. Please rephrase."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=True)
