import os
import uuid
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from supabase import create_client, Client
from pywebpush import webpush, WebPushException

app = Flask(__name__)

# --- PWA BRIDGE ROUTES (Required for PWABuilder) ---
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

def add_log(username, activity):
    supabase.table('logs').insert({"username": username, "activity": activity}).execute()

@app.route('/api/vapid_public_key', methods=['GET'])
def vapid_key():
    return jsonify({"public_key": VAPID_PUBLIC_KEY}), 200

@app.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.json
    username = data.get('username')
    sub_info = data.get('sub_info')
    
    supabase.table('subscriptions').delete().eq('username', username).execute()
    supabase.table('subscriptions').insert({"username": username, "sub_info": sub_info}).execute()
    return jsonify({"status": "success"}), 200

def broadcast_notification(title, body, exclude_user=None):
    subs = supabase.table('subscriptions').select('*').execute().data
    for sub in subs:
        if sub['username'] == exclude_user:
            continue
        try:
            webpush(
                subscription_info=sub['sub_info'],
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CLAIM_EMAIL}
            )
        except Exception as e:
            print(f"Push failed for {sub['username']}: {e}")

@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        response = supabase.table('logs').select('*').order('created_at', desc=True).limit(10).execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/treasures', methods=['GET', 'POST'])
def handle_treasures():
    if request.method == 'GET':
        return jsonify(supabase.table('treasures').select('*').execute().data), 200
    else:
        lat, lng = float(request.form.get('lat')), float(request.form.get('lng'))
        title = request.form.get('title', 'Mystery Cache')
        desc, creator = request.form.get('description'), request.form.get('creator')
        marker_url = request.form.get('marker_url', 'https://cdn-icons-png.flaticon.com/512/3175/3175218.png')
        
        image_url = ""
        # RESTORED: Image Upload Logic
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                file_ext = file.filename.split('.')[-1]
                file_name = f"{uuid.uuid4().hex}.{file_ext}"
                supabase.storage.from_('cache-images').upload(file_name, file.read(), {"content-type": file.content_type})
                image_url = supabase.storage.from_('cache-images').get_public_url(file_name)

        supabase.table('treasures').insert({
            "lat": lat, "lng": lng, "title": title, "description": desc, 
            "image_url": image_url, "creator": creator, "marker_url": marker_url
        }).execute()
        
        add_log(creator, f"hid a new cache: {title}")
        broadcast_notification("New Cache Alert! 🚨", f"{creator} just hid '{title}'. Open the map to find it!", exclude_user=creator)
        return jsonify({"message": "Success"}), 200

# RESTORED: Edit and Delete Caches logic
@app.route('/api/treasures/<int:t_id>', methods=['PUT', 'DELETE'])
def manage_treasure(t_id):
    username = request.json.get('username')
    t_res = supabase.table('treasures').select('creator, title').eq('id', t_id).execute()
    if not t_res.data or t_res.data[0]['creator'] != username:
        return jsonify({"error": "Unauthorized"}), 403

    if request.method == 'DELETE':
        try:
            supabase.table('claims').delete().eq('treasure_id', t_id).execute()
            del_res = supabase.table('treasures').delete().eq('id', t_id).execute()
            add_log(username, f"removed their cache: {t_res.data[0]['title']}")
            return jsonify({"status": "deleted"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    elif request.method == 'PUT':
        new_desc = request.json.get('description')
        supabase.table('treasures').update({"description": new_desc}).eq('id', t_id).execute()
        return jsonify({"status": "updated"}), 200

# RESTORED: Claim tracking with difficulty rating
@app.route('/api/claim', methods=['POST'])
def claim_treasure():
    data = request.json
    username = data.get('username')
    treasure_id = data.get('treasure_id')
    review = data.get('review', '')
    difficulty = int(data.get('difficulty', 1))
    
    t_res = supabase.table('treasures').select('id, title, creator').eq('id', treasure_id).execute()
    if not t_res.data: return jsonify({"error": "Not found in database"}), 404
    
    if t_res.data[0]['creator'] == username:
        return jsonify({"error": "You cannot claim your own cache!"}), 403
    
    cache_title = t_res.data[0]['title']
    
    supabase.table('claims').insert({
        "username": username, "treasure_id": t_res.data[0]['id'], "review": review, "difficulty": difficulty
    }).execute()
    
    add_log(username, f"found {cache_title} and rated it {difficulty} Stars!")
    broadcast_notification("Cache Discovered! 🗺️", f"{username} just found '{cache_title}'!")
    return jsonify({"status": "success"}), 201

# RESTORED: Advanced Leaderboard Math
@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    claims_res = supabase.table('claims').select('username').execute()
    hides_res = supabase.table('treasures').select('creator').execute()
    
    stats = {}
    for item in claims_res.data:
        u = item['username']
        stats[u] = stats.get(u, {'found': 0, 'hidden': 0})
        stats[u]['found'] += 1
        
    for item in hides_res.data:
        u = item['creator']
        stats[u] = stats.get(u, {'found': 0, 'hidden': 0})
        stats[u]['hidden'] += 1

    leaderboard = []
    for u, data in stats.items():
        score = (data['found'] * 10) + (data['hidden'] * 20)
        leaderboard.append({"username": u, "found": data['found'], "hidden": data['hidden'], "score": score})

    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    return jsonify(leaderboard), 200

# RESTORED: Profile Badges Logic
@app.route('/api/profile/<username>', methods=['GET'])
def get_profile(username):
    found_data = supabase.table('claims').select('id').eq('username', username).execute().data
    hidden_data = supabase.table('treasures').select('id').eq('creator', username).execute().data
    
    found = len(found_data)
    hidden = len(hidden_data)
    rank = "Master 👑" if (found + hidden*2) > 25 else "Novice 🌱"
    
    badges = []
    if found >= 1: badges.append("🧭 First Find")
    if found >= 5: badges.append("🦊 Expert Tracker")
    if hidden >= 1: badges.append("🗺️ Trailblazer")
    if hidden >= 5: badges.append("🏛️ Local Legend")

    return jsonify({"found": found, "hidden": hidden, "rank": rank, "badges": badges}), 200

# RESTORED: Full Friend Request System
@app.route('/api/friends/<username>', methods=['GET'])
def get_friends(username):
    all_f = supabase.table('friends').select('*').or_(f"requester.eq.{username},receiver.eq.{username}").execute().data
    friends = [f['requester'] if f['receiver'] == username else f['receiver'] for f in all_f if f['status'] == 'accepted']
    pending = [f['requester'] for f in all_f if f['status'] == 'pending' and f['receiver'] == username]
    return jsonify({"friends": friends, "pending": pending}), 200

@app.route('/api/friend/request', methods=['POST'])
def req():
    supabase.table('friends').insert({"requester": request.json['requester'], "receiver": request.json['receiver'], "status": "pending"}).execute()
    return jsonify({"message": "Sent"}), 200

@app.route('/api/friend/respond', methods=['POST'])
def res():
    d = request.json
    if d['action'] == 'accept': supabase.table('friends').update({"status": "accepted"}).eq('requester', d['requester']).eq('receiver', d['receiver']).execute()
    else: supabase.table('friends').delete().eq('requester', d['requester']).eq('receiver', d['receiver']).execute()
    return jsonify({"message": "Done"}), 200

# --- SAFE SERVER DEPLOYMENT GUARD ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)