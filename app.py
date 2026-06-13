import os
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from collections import Counter # Added to help count claims

app = Flask(__name__)

# Initialize Supabase clients
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return render_template('index.html')

# --- Existing Routes ---
@app.route('/api/treasures', methods=['GET'])
def get_treasures():
    try:
        response = supabase.table('treasures').select('*').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/treasures', methods=['POST'])
def add_treasure():
    data = request.get_json()
    try:
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
        riddle = data.get('riddle')
        response = supabase.table('treasures').insert({"lat": lat, "lng": lng, "riddle": riddle}).execute()
        return jsonify({"message": "Cache successfully hidden!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/claims', methods=['POST'])
def claim_treasure():
    try:
        data = request.json
        username = data.get('username')
        treasure_id = data.get('treasure_id')
        
        response = supabase.table('claims').insert({"username": username, "treasure_id": int(treasure_id)}).execute()
        return jsonify({"status": "success", "message": f"Cache claimed by {username}!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- NEW: Leaderboard Route ---
@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    try:
        # Fetch all claims
        response = supabase.table('claims').select('username').execute()
        
        # Count occurrences of each username
        counts = Counter([item['username'] for item in response.data])
        
        # Convert to a list of dicts for the frontend
        leaderboard = [{"username": name, "count": count} for name, count in counts.most_common()]
        return jsonify(leaderboard), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)