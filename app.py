
import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

SUPABASE_URL = "https://wufjrdwmoyspqmivjdog.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/treasures', methods=['GET'])
def get_treasures():
    try:
        response = supabase.table('treasures').select('*').execute()
        formatted_treasures = []
        for row in response.data:
            formatted_treasures.append({
                "id": row["id"],
                "lat": row["latitude"],
                "lng": row["longitude"],
                "riddle": row["riddle"]
            })
        return jsonify(formatted_treasures), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/treasures', methods=['POST'])
def add_treasure():
    data = request.json
    try:
        new_row = {
            "latitude": data['lat'],
            "longitude": data['lng'],
            "riddle": data['riddle']
        }
        response = supabase.table('treasures').insert(new_row).execute()
        return jsonify({"status": "success", "data": response.data[0]}), 201
    except Exception as e:
        print("💥 BACKEND CRASH REPORT:", str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)