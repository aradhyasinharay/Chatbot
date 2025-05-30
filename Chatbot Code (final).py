
from flask import Flask, request, jsonify
import threading

app = Flask("PowerPlus")

# Your QA knowledge base example
qa_data = {
    "Power Theft": {
        "Tampering with meter": "Tampering with meter is illegal and punishable.",
        "Illegal tapping": "Illegal tapping is a major offense under the electricity act."
    },
    "Demand": {
        "Load forecast": "Load forecast involves predicting future electricity demand.",
        "Peak hours": "Peak hours are usually from 6 PM to 10 PM."
    },
    "Plant Generating": {
        "Thermal plant": "Thermal plants generate electricity using coal or gas.",
        "Solar plant": "Solar plants use photovoltaic cells to generate power."
    },
    "General": {
        "Hello": "Hi there! Welcome to PowerPlus, how can I help you today?",
        "Hi": "Hello! Welcome to PowerPlus, how can I help you today?",
        "How are you": "I'm just a chatbot, but I'm functioning well!",
        "What is PowerPlus": "PowerPlus is a premium energy solution provider.",
        "Bye": "Goodbye! Have a great day!"
    }
}


user_state = {"stage": "initial", "topic": None}

@app.route("/get", methods=["GET", "POST"])
def handle_chat():
    if request.method == "GET":
        user_input = request.args.get("msg", "").strip().lower()
    else:
        user_input = request.form.get("msg", "").strip().lower()

    global user_state

    if user_state["stage"] == "initial" and user_input in ["hi", "hello"]:
        user_state["stage"] = "topic_selection"
        topics = list(qa_data.keys())
        topic_list = "\n".join(f"- {t}" for t in topics)
        return jsonify({"response": f"Please choose a topic:\n{topic_list}"})

    elif user_state["stage"] == "topic_selection":
        selected_topic = user_input.title()
        if selected_topic in qa_data:
            user_state["topic"] = selected_topic
            user_state["stage"] = "subtopic_selection"
            subtopics = list(qa_data[selected_topic].keys())
            sub_list = "\n".join(f"- {s}" for s in subtopics)
            return jsonify({"response": f"You selected *{selected_topic}*.\nChoose a subtopic:\n{sub_list}"})
        else:
            return jsonify({"response": "Invalid topic. Try again."})

    elif user_state["stage"] == "subtopic_selection":
        topic = user_state["topic"]
        subtopics = qa_data[topic]
        matched_sub = next((k for k in subtopics if user_input in k.lower()), None)
        if matched_sub:
            answer = subtopics[matched_sub]
            user_state["stage"] = "initial"  # reset state after answer
            return jsonify({"response": f"{answer}\n\nType 'hi' to start again."})
        else:
            return jsonify({"response": "Subtopic not found. Try again or type 'hi' to restart."})

    else:
        return jsonify({"response": "Please type 'hi' to begin."})

# Run Flask in a separate thread on port 5050 to avoid conflicts
def run_flask():
    app.run(port=5000)

threading.Thread(target=run_flask, daemon=True).start()
print("Flask app running on port 5000")

