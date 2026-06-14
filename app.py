import os
import uuid
from flask import Flask, render_template, request, jsonify
from supabase import create_client, Client
from collections import Counter

app = Flask(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Geocatcher", "short_name": "Geocatcher", "start_url": "/",
        "display": "standalone", "background_color": "#1a1a2e", "theme_color": "#1a1a2e",
        "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/2857/2857355.png", "sizes": "512x512", "type": "image/png"}]
    }), 200

# --- Logs Helper ---
def add_log(username, activity):
    supabase.table('logs').insert({"username": username, "activity": activity}).execute()

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
        # POST: Upload logic
        lat, lng = float(request.form.get('lat')), float(request.form.get('lng'))
        title = request.form.get('title', 'Mystery Cache')
        desc, creator = request.form.get('description'), request.form.get('creator')
        
        image_url = ""
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                file_ext = file.filename.split('.')[-1]
                file_name = f"{uuid.uuid4().hex}.{file_ext}"
                supabase.storage.from_('cache-images').upload(file_name, file.read(), {"content-type": file.content_type})
                image_url = supabase.storage.from_('cache-images').get_public_url(file_name)

        supabase.table('treasures').insert({"lat": lat, "lng": lng, "title": title, "description": desc, "image_url": image_url, "creator": creator}).execute()
        add_log(creator, f"hid a new cache: {title}")
        return jsonify({"message": "Success"}), 200

@app.route('/api/claim', methods=['POST'])
def claim_treasure():
    data = request.json
    username, lat, lng = data.get('username'), data.get('lat'), data.get('lng')
    t_res = supabase.table('treasures').select('id, title').eq('lat', lat).eq('lng', lng).execute()
    if not t_res.data: return jsonify({"error": "Not found"}), 404
    
    supabase.table('claims').insert({"username": username, "treasure_id": t_res.data[0]['id']}).execute()
    add_log(username, f"found {t_res.data[0]['title']}")
    return jsonify({"status": "success"}), 201

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():
    res = supabase.table('claims').select('username').execute()
    counts = Counter([item['username'] for item in res.data])
    return jsonify([{"username": name, "count": count} for name, count in counts.most_common()]), 200

@app.route('/api/profile/<username>', methods=['GET'])
def get_profile(username):
    found = len(supabase.table('claims').select('id').eq('username', username).execute().data)
    hidden = len(supabase.table('treasures').select('id').eq('creator', username).execute().data)
    rank = "Master 👑" if (found + hidden*2) > 25 else "Novice 🌱"
    return jsonify({"found": found, "hidden": hidden, "rank": rank}), 200

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)