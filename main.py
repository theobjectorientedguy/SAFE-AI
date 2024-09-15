import os
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
from groq import Groq
from dotenv import load_dotenv


app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
socketio = SocketIO(app)

client = Groq(
    api_key="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",
)

rooms = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in rooms:
            break
    
    return code

def check_and_filter_message(message, checks):
    """Check the message using the Groq model for issues and filter it if necessary."""
    if not checks:
        print("No checks selected. Returning original message.")  # Debug log
        return message

    # Construct the prompt based on selected checks
    prompt = (
        f"You are a content moderator tasked with making internet chat safe. Please strictly moderate the following message based on these checks: {', '.join(checks)}.\n"
        f"Message: {message}\n\n"
        "Instructions:\n"
        "1. If the message contains inappropriate content, replace the inappropriate parts with more acceptable content.\n"
        "2. If the message contains potential spam or sensitive information leaks, hide that information or add a warning sign at the beginning of the message.\n"
        "3. If the message does not violate any of the specified checks, return the message unchanged.\n\n"
        "Output only the moderated message. Do not include any additional information or explanation."
    )
    
    print(f"Prompt for Groq model: {prompt}")  # Debug log
    
    # Use the Groq model to process the message
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-70b-versatile"  # Adjust the model as needed
    )
    
    # Extract the generated text
    filtered_message = chat_completion.choices[0].message.content.strip()
    print(f"Filtered message: {filtered_message}")  # Debug log
    
    if filtered_message != message:
       filtered_message += " (Filtered by SafeAI)"

    return filtered_message

@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:
            return render_template("home.html", error="Please enter a name.", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="Please enter a room code.", code=code, name=name)
        
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="Room does not exist.", code=code, name=name)
        
        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return 
    
    content = {
        "name": session.get("name"),
        "message": data["data"]
    }

    # Get the user's selected checks
    checks = data.get('checks', [])
    
    # Process the message with Groq-based filtering
    filtered_message = check_and_filter_message(content["message"], checks)
    content["message"] = filtered_message
    
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} sent: {filtered_message}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return
    
    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]
    
    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} has left the room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True)
