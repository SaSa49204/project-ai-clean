from flask import Flask, request, jsonify
from faqbot import FAQBot
import os
import uuid
import datetime
import jwt
from flask_cors import CORS

app = Flask(__name__)

# ✅ CORS مفتوح لأي frontend 🔥
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

bot = FAQBot("data.csv")

# =====================================
# STORAGE
# =====================================
sessions = {}

# =====================================
# GET STUDENT ID FROM TOKEN
# =====================================
def get_student_id_from_token(token):
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})

        student_id = (
            decoded.get("student_id")
            or decoded.get("id")
            or decoded.get("sub")
            or decoded.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier")
        )

        return student_id

    except Exception as e:
        print("JWT ERROR:", str(e))
        return None

# =====================================
# CREATE SESSION
# =====================================
@app.route("/chat/session", methods=["POST"])
def create_session():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization missing"}), 401

        token = auth_header.replace("Bearer ", "")
        bot.token = token

        student_id = get_student_id_from_token(token)
        if student_id is None:
            return jsonify({"error": "Invalid token"}), 401

        session_id = str(uuid.uuid4())

        if student_id not in sessions:
            sessions[student_id] = {}

        sessions[student_id][session_id] = {
            "name": "New Chat",
            "messages": [],
            "updated_at": datetime.datetime.now(),
            "last_message": ""
        }

        return jsonify({"session_id": session_id})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================
# CHAT
# =====================================
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()

        question = data.get("question")
        session_id = data.get("session_id")

        if not question:
            return jsonify({"error": "Question required"}), 400

        # 🔥 FIX: session_id check
        if not session_id:
            return jsonify({"error": "session_id required"}), 400

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization missing"}), 401

        token = auth_header.replace("Bearer ", "")
        bot.token = token

        student_id = get_student_id_from_token(token)
        if student_id is None:
            return jsonify({"error": "Invalid token"}), 401

        if student_id not in sessions or session_id not in sessions[student_id]:
            return jsonify({"error": "Invalid session"}), 400

        result = bot.answer(question, student_id)

        # 🔥 logging مهم
        print("QUESTION:", question)
        print("ANSWER:", result)

        sessions[student_id][session_id]["messages"].append({
            "q": question,
            "a": result.get("answer", "No response")
        })

        # 🔥 FIX: title يتعمل مرة واحدة بس
        if (
            sessions[student_id][session_id]["name"] == "New Chat"
            and len(sessions[student_id][session_id]["messages"]) == 1
        ):
            ai_title = bot.generate_title(question)
            sessions[student_id][session_id]["name"] = ai_title[:30]

        sessions[student_id][session_id]["updated_at"] = datetime.datetime.now()
        sessions[student_id][session_id]["last_message"] = question

        return jsonify(result)

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500

# =====================================
# LIST SESSIONS
# =====================================
@app.route("/chat/sessions", methods=["GET"])
def list_sessions():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization missing"}), 401

        token = auth_header.replace("Bearer ", "")
        bot.token = token

        student_id = get_student_id_from_token(token)
        if student_id is None:
            return jsonify({"error": "Invalid token"}), 401

        user_sessions = sessions.get(student_id, {})

        sorted_sessions = sorted(
            user_sessions.items(),
            key=lambda x: x[1].get("updated_at"),
            reverse=True
        )

        result = []

        for sid, data in sorted_sessions:
            result.append({
                "session_id": sid,
                "name": data["name"],
                "last_message": data.get("last_message", "")
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================
# GET SESSION WITH MESSAGES 🔥
# =====================================
@app.route("/chat/session/<session_id>", methods=["GET"])
def get_session(session_id):
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization missing"}), 401

        token = auth_header.replace("Bearer ", "")
        bot.token = token

        student_id = get_student_id_from_token(token)
        if student_id is None:
            return jsonify({"error": "Invalid token"}), 401

        if student_id not in sessions or session_id not in sessions[student_id]:
            return jsonify({"error": "Session not found"}), 404

        session_data = sessions[student_id][session_id]

        return jsonify({
            "session_id": session_id,
            "name": session_data["name"],
            "messages": session_data["messages"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================
# DELETE ONE SESSION
# =====================================
@app.route("/chat/session/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization missing"}), 401

        token = auth_header.replace("Bearer ", "")
        bot.token = token

        student_id = get_student_id_from_token(token)
        if student_id is None:
            return jsonify({"error": "Invalid token"}), 401

        if student_id in sessions and session_id in sessions[student_id]:
            del sessions[student_id][session_id]
            return jsonify({"message": "Session deleted successfully"})

        return jsonify({"error": "Session not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================
# DELETE ALL SESSIONS 🔥
# =====================================
@app.route("/chat/sessions", methods=["DELETE"])
def delete_all_sessions():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization missing"}), 401

        token = auth_header.replace("Bearer ", "")
        bot.token = token

        student_id = get_student_id_from_token(token)
        if student_id is None:
            return jsonify({"error": "Invalid token"}), 401

        sessions[student_id] = {}

        return jsonify({"message": "All sessions deleted"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================
# RENAME SESSION
# =====================================
@app.route("/chat/session/<session_id>", methods=["PUT"])
def rename_session(session_id):
    try:
        data = request.get_json()
        new_name = data.get("name")

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization missing"}), 401

        token = auth_header.replace("Bearer ", "")
        bot.token = token

        student_id = get_student_id_from_token(token)
        if student_id is None:
            return jsonify({"error": "Invalid token"}), 401

        if student_id in sessions and session_id in sessions[student_id]:
            sessions[student_id][session_id]["name"] = new_name
            return jsonify({"message": "Session renamed"})

        return jsonify({"error": "Session not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =====================================
# HEALTH
# =====================================
@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "message": "Guide Bot is working 🚀"
    })

# =====================================
# RUN
# =====================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)