import os
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from supabase import create_client, Client
from pywebpush import webpush, WebPushException

app = Flask(__name__)

# --- PWA BRIDGE ROUTES ---
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json', mimetype='application/json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory('.', 'sw.js', mimetype='application/javascript')

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY")
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL")

@app.route('/')
def home():
    return render_template('index.html')

# --- LOGGING ---
def add_log(username, activity):
    supabase.table('logs').insert({"username": username, "activity": activity}).execute()

# --- PUSH NOTIFICATIONS ---
@app.route('/api/vapid_public_key', methods=['GET'])
def vapid_key():
    return jsonify({"public_key": VAPID_PUBLIC_KEY}), 200

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    supabase.table('subscriptions').delete().eq('username', data['username']).execute()
    supabase.table('subscriptions').insert({"username": data['username'], "sub_info": data['sub_info']}).execute()
    return jsonify({"status": "success"}), 200

def broadcast_notification(title, body, exclude_user=None):
    subs = supabase.table('subscriptions').select('*').execute().data
    for sub in subs:
        if sub['username'] == exclude_user: continue
        try:
            webpush(subscription_info=sub['sub_info'], data=json.dumps({"title": title, "body": body}), 
                    vapid_private_key=VAPID_PRIVATE_KEY, vapid_claims={"sub": VAPID_CLAIM_EMAIL})
        except Exception as e: print(f"Push failed: {e}")

# --- TREASURE HUNT LOGIC ---
@app.route('/api/treasures', methods=['GET', 'POST'])
def handle_treasures():
    if request.method == 'GET':
        return jsonify(supabase.table('treasures').select('*').execute().data), 200
    lat, lng = float(request.form.get('lat')), float(request.form.get('lng'))
    title, desc, creator = request.form.get('title'), request.form.get('description'), request.form.get('creator')
    marker_url = request.form.get('marker_url', 'https://cdn-icons-png.flaticon.com/512/3175/3175218.png')
    
    supabase.table('treasures').insert({"lat": lat, "lng": lng, "title": title, "description": desc, "creator": creator, "marker_url": marker_url}).execute()
    add_log(creator, f"hid: {title}")
    broadcast_notification("New Cache! 🚨", f"{creator} hid '{title}'!")
    return jsonify({"message": "Success"}), 200

@app.route('/api/claim', methods=['POST'])
def claim_treasure():
    data = request.json
    supabase.table('claims').insert({"username": data['username'], "treasure_id": data['treasure_id']}).execute()
    return jsonify({"status": "success"}), 201

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    return jsonify(supabase.table('treasures').select('*').execute().data), 200

@app.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify(supabase.table('logs').select('*').order('created_at', desc=True).limit(10).execute().data), 200

# --- USER PROFILE & FRIENDS ---
@app.route('/api/profile/<username>', methods=['GET'])
def get_profile(username):
    found = len(supabase.table('claims').select('id').eq('username', username).execute().data)
    hidden = len(supabase.table('treasures').select('id').eq('creator', username).execute().data)
    return jsonify({"found": found, "hidden": hidden, "rank": "Master 👑" if (found + hidden*2) > 25 else "Novice 🌱"}), 200

@app.route('/api/friends/<username>', methods=['GET'])
def get_friends(username):
    all_f = supabase.table('friends').select('*').or_(f"requester.eq.{username},receiver.eq.{username}").execute().data
    friends = [f['requester'] if f['receiver'] == username else f['receiver'] for f in all_f if f['status'] == 'accepted']
    return jsonify({"friends": friends}), 200

# --- SERVER START ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)