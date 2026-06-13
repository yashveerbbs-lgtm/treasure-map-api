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

# --- Hide a New Treasure (UPDATED with 'creator') ---
@app.route('/api/treasures', methods=['POST'])
def add_treasure():
    data = request.get_json()
    try:
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
        title = data.get('title', 'Mystery Cache')
        description = data.get('description', 'No description provided.')
        image_url = data.get('image_url', '')
        creator = data.get('creator', 'Unknown') # Now we track who hid it!
        
        response = supabase.table('treasures').insert({
            "lat": lat, 
            "lng": lng, 
            "title": title,
            "description": description,
            "image_url": image_url,
            "creator": creator
        }).execute()
        
        return jsonify({"message": "Cache successfully hidden!"}), 200
    except Exception as e:
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

        treasure_response = supabase.table('treasures').select('id').eq('lat', lat).eq('lng', lng).execute()
        
        if not treasure_response.data:
            return jsonify({"error": "Treasure not found in database"}), 404
            
        treasure_id = treasure_response.data[0]['id']
        response = supabase.table('claims').insert({"username": username, "treasure_id": treasure_id}).execute()
        
        return jsonify({"status": "success", "message": f"Cache claimed by {username}!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Leaderboard ---
@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    try:
        response = supabase.table('claims').select('username').execute()
        counts = Counter([item['username'] for item in response.data])
        leaderboard = [{"username": name, "count": count} for name, count in counts.most_common()]
        return jsonify(leaderboard), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# NEW FEATURES: PROFILES & FRIENDS
# ==========================================

# --- Get Profile Stats ---
@app.route('/api/profile/<username>', methods=['GET'])
def get_profile(username):
    try:
        # Get claims count
        claims_response = supabase.table('claims').select('id').eq('username', username).execute()
        found_count = len(claims_response.data)
        
        # Get hidden count
        hidden_response = supabase.table('treasures').select('id').eq('creator', username).execute()
        hidden_count = len(hidden_response.data)
        
        # Calculate Rank
        total_points = found_count + (hidden_count * 2) # Hiding gives double points!
        if total_points < 3: rank = "Novice Hider 🌱"
        elif total_points < 10: rank = "Radar Tech 📡"
        elif total_points < 25: rank = "Pro Explorer 🗺️"
        else: rank = "Master Geocatcher 👑"

        return jsonify({
            "username": username,
            "found": found_count,
            "hidden": hidden_count,
            "rank": rank
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Send Friend Request ---
@app.route('/api/friend/request', methods=['POST'])
def send_friend_request():
    try:
        data = request.json
        requester = data.get('requester')
        receiver = data.get('receiver')
        
        # Prevent sending to yourself
        if requester == receiver:
            return jsonify({"error": "You can't friend yourself!"}), 400

        supabase.table('friends').insert({
            "requester": requester,
            "receiver": receiver,
            "status": "pending"
        }).execute()
        
        return jsonify({"message": "Friend request sent!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Respond to Friend Request ---
@app.route('/api/friend/respond', methods=['POST'])
def respond_friend_request():
    try:
        data = request.json
        requester = data.get('requester')
        receiver = data.get('receiver')
        action = data.get('action') # 'accept' or 'reject'
        
        if action == 'accept':
            supabase.table('friends').update({"status": "accepted"}).eq('requester', requester).eq('receiver', receiver).execute()
            return jsonify({"message": "Friend request accepted!"}), 200
        else:
            supabase.table('friends').delete().eq('requester', requester).eq('receiver', receiver).execute()
            return jsonify({"message": "Friend request rejected!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Get Friend List & Pending Requests ---
@app.route('/api/friends/<username>', methods=['GET'])
def get_friends(username):
    try:
        # Get requests where you are the receiver
        received = supabase.table('friends').select('*').eq('receiver', username).execute()
        # Get requests where you are the requester
        sent = supabase.table('friends').select('*').eq('requester', username).execute()
        
        all_friends = received.data + sent.data
        
        accepted_friends = []
        pending_requests = []
        
        for f in all_friends:
            if f['status'] == 'accepted':
                # If they accepted, grab the other person's name
                friend_name = f['requester'] if f['receiver'] == username else f['receiver']
                accepted_friends.append(friend_name)
            elif f['status'] == 'pending' and f['receiver'] == username:
                # Someone wants to be your friend
                pending_requests.append(f['requester'])

        return jsonify({
            "friends": accepted_friends,
            "pending": pending_requests
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)