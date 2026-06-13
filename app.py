import os
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from collections import Counter

app = Flask(__name__)

# Initialize Supabase clients
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return render_template('index.html')

# --- Fetch All Treasures ---
@app.route('/api/treasures', methods=['GET'])
def get_treasures():
    try:
        response = supabase.table('treasures').select('*').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Hide a New Treasure ---
@app.route('/api/treasures', methods=['POST'])
def add_treasure():
    data = request.get_json()
    try:
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
        
        # Grab the new details, using defaults if the user leaves them blank
        title = data.get('title', 'Mystery Cache')
        description = data.get('description', 'No description provided.')
        image_url = data.get('image_url', '')
        
        # Save everything to the database
        response = supabase.table('treasures').insert({
            "lat": lat, 
            "lng": lng, 
            "title": title,
            "description": description,
            "image_url": image_url
        }).execute()
        
        return jsonify({"message": "Cache successfully hidden!"}), 200
    except Exception as e:
        print("Error adding treasure:", str(e))
        return jsonify({"error": str(e)}), 500

# --- Claim a Treasure ---
@app.route('/api/claim', methods=['POST'])
def claim_treasure():
    try:
        data = request.json
        username = data.get('username')
        lat = data.get('lat')
        lng = data.get('lng')
        
        if not username:
            return jsonify({"error": "Username is required"}), 400

        # Step 1: Look up the treasure's ID using its GPS coordinates
        treasure_response = supabase.table('treasures').select('id').eq('lat', lat).eq('lng', lng).execute()
        
        if not treasure_response.data:
            return jsonify({"error": "Treasure not found in database"}), 404
            
        treasure_id = treasure_response.data[0]['id']
        
        # Step 2: Insert the claim into the database
        response = supabase.table('claims').insert({"username": username, "treasure_id": treasure_id}).execute()
        
        return jsonify({"status": "success", "message": f"Cache claimed by {username}!"}), 201
        
    except Exception as e:
        print("Error saving claim:", str(e))
        return jsonify({"error": str(e)}), 500

# --- Leaderboard Route ---
@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    try:
        # Fetch all claims
        response = supabase.table('claims').select('username').execute()
        
        # Count occurrences of each username
        counts = Counter([item['username'] for item in response.data])
        
        # Convert to a list of dicts for the frontend, sorted automatically by Counter
        leaderboard = [{"username": name, "count": count} for name, count in counts.most_common()]
        return jsonify(leaderboard), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)