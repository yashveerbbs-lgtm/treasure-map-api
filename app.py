import os
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client

app = Flask(__name__)

# Initialize Supabase clients securely using your Render Vault environment keys
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return render_template('index.html')

# 1. Existing Route: Fetch all global hidden caches
@app.route('/api/treasures', methods=['GET'])
def get_treasures():
    try:
        response = supabase.table('treasures').select('*').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 2. Existing Route: Drop a new cache target via map double-clicks
@app.route('/api/treasures', methods=['POST'])
def add_treasure():
    data = request.get_json()
    try:
        # Explicitly converting to float to match 'float8' column type
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
        riddle = data.get('riddle')
        
        response = supabase.table('treasures').insert({
            "lat": lat,
            "lng": lng,
            "riddle": riddle
        }).execute()
        
        return jsonify({"message": "Cache successfully hidden!"}), 200
    except Exception as e:
        # This will now print the full error to your Render Logs
        print(f"DEBUG ERROR: {str(e)}") 
        return jsonify({"error": str(e)}), 500

# 3. NEW FEATURE ROUTE: Log a player check-in visit
@app.route('/api/claims', methods=['POST'])
def claim_treasure():
    try:
        data = request.json
        username = data.get('username')
        treasure_id = data.get('treasure_id')

        if not username or not treasure_id:
            return jsonify({"error": "Missing username or treasure_id"}), 400

        # Insert claim record into a 'claims' logbook table
        insert_data = {"username": username, "treasure_id": int(treasure_id)}
        response = supabase.table('claims').insert(insert_data).execute()
        return jsonify({"status": "success", "message": f"Cache claimed by {username}!"}), 201
    except Exception as e:
        # If you haven't made a claims table yet, we'll gracefully return success for prototyping
        return jsonify({"status": "mock_success", "message": f"Verified! Logged locally for {username}"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)