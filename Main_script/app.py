from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import asyncio
import json
import websockets
from threading import Thread
from datetime import datetime
import uuid
import time

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# État global
rooms = {}
websocket_clients = {}
video_files = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def cleanup_video_file(filename):
    """Supprime un fichier vidéo du disque et de la tracking"""
    try:
        if filename in video_files:
            filepath = video_files[filename]['path']
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"🗑️ Fichier supprimé: {filename}")
            del video_files[filename]
            return True
    except Exception as e:
        print(f"❌ Erreur suppression {filename}: {e}")
    return False

def check_video_cleanup():
    """Vérifie et nettoie les vidéos qui ne sont plus utilisées"""
    to_delete = []
    
    for filename, info in video_files.items():
        if len(info['rooms_using']) == 0:
            if time.time() - info.get('last_used', info['upload_time']) > 30:
                to_delete.append(filename)
    
    for filename in to_delete:
        cleanup_video_file(filename)
    
    if to_delete:
        print(f"🧹 Nettoyage: {len(to_delete)} fichier(s) supprimé(s)")

def mark_video_played(video_url, room_id):
    """Marque une vidéo comme jouée et retire la room de la liste des utilisateurs"""
    if video_url.startswith('/uploads/'):
        filename = os.path.basename(video_url)
        if filename in video_files:
            video_files[filename]['rooms_using'].discard(room_id)
            video_files[filename]['last_used'] = time.time()
            print(f"✅ Vidéo {filename} jouée dans {room_id}")
            
            if len(video_files[filename]['rooms_using']) == 0:
                print(f"⏳ {filename} sera supprimé dans 30s si non réutilisé")

# ==================== Routes Flask ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Sert les vidéos uploadées avec support du streaming"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/api/upload', methods=['POST'])
def upload_video():
    """Endpoint pour uploader des vidéos"""
    try:
        if 'video' not in request.files:
            return jsonify({'error': 'Aucune vidéo'}), 400
        
        file = request.files['video']
        room_id = request.form.get('room_id', 'default')
        added_by = request.form.get('added_by', 'Anonyme')
        
        if file.filename == '':
            return jsonify({'error': 'Nom de fichier vide'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Format non supporté'}), 400
        
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        file.save(filepath)
        
        video_files[unique_filename] = {
            'path': filepath,
            'rooms_using': {room_id},
            'upload_time': time.time(),
            'original_name': file.filename
        }
        
        video = {
            'id': str(uuid.uuid4()),
            'url': f'/uploads/{unique_filename}',
            'type': 'file',
            'addedAt': datetime.now().isoformat(),
            'addedBy': added_by,
            'originalName': file.filename
        }
        
        if room_id not in rooms:
            rooms[room_id] = {'clients': set(), 'queue': []}
        
        rooms[room_id]['queue'].append(video)
        
        asyncio.run(broadcast_to_room(room_id, {
            'action': 'new_video',
            'video': video,
            'queue': rooms[room_id]['queue']
        }))
        
        print(f"✅ Upload: {file.filename} → {unique_filename} (room: {room_id})")
        
        return jsonify({
            'success': True,
            'video': video,
            'message': 'Vidéo uploadée avec succès'
        }), 200
    
    except Exception as e:
        print(f"❌ Erreur upload: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/add_url', methods=['POST'])
def add_url():
    """Endpoint pour ajouter des URLs"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        room_id = data.get('room_id', 'default')
        added_by = data.get('added_by', 'Anonyme')
        
        if not url:
            return jsonify({'error': 'URL manquante'}), 400
        
        is_youtube = 'youtube.com' in url or 'youtu.be' in url
        
        video = {
            'id': str(uuid.uuid4()),
            'url': url,
            'type': 'youtube' if is_youtube else 'url',
            'addedAt': datetime.now().isoformat(),
            'addedBy': added_by
        }
        
        if room_id not in rooms:
            rooms[room_id] = {'clients': set(), 'queue': []}
        
        rooms[room_id]['queue'].append(video)
        
        asyncio.run(broadcast_to_room(room_id, {
            'action': 'new_video',
            'video': video,
            'queue': rooms[room_id]['queue']
        }))
        
        return jsonify({
            'success': True,
            'video': video
        }), 200
    
    except Exception as e:
        print(f"❌ Erreur add_url: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/clear', methods=['POST'])
def clear_room(room_id):
    """Vider complètement la queue d'une room"""
    try:
        if room_id in rooms:
            for video in rooms[room_id]['queue']:
                mark_video_played(video.get('url'), room_id)
            
            rooms[room_id]['queue'] = []
            
            asyncio.run(broadcast_to_room(room_id, {
                'action': 'clear_all',
                'queue': []
            }))
            
            print(f"🗑️ Queue vidée pour '{room_id}'")
            
            return jsonify({
                'success': True,
                'message': 'Queue vidée'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Room non trouvée'
            }), 404
    
    except Exception as e:
        print(f"❌ Erreur clear: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/skip', methods=['POST'])
def skip_video(room_id):
    """Skip la vidéo en cours"""
    try:
        if room_id in rooms and rooms[room_id]['queue']:
            skipped_video = rooms[room_id]['queue'].pop(0)
            mark_video_played(skipped_video.get('url'), room_id)
            
            asyncio.run(broadcast_to_room(room_id, {
                'action': 'video_skipped',
                'queue': rooms[room_id]['queue']
            }))
            
            print(f"⏭️ Vidéo skippée dans '{room_id}'")
            
            return jsonify({
                'success': True,
                'message': 'Vidéo skippée'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Aucune vidéo à skipper'
            }), 404
    
    except Exception as e:
        print(f"❌ Erreur skip: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rooms/<room_id>/queue', methods=['GET'])
def get_queue(room_id):
    """Récupérer la queue d'une room"""
    if room_id in rooms:
        return jsonify({'queue': rooms[room_id]['queue']}), 200
    return jsonify({'queue': []}), 200

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Statistiques du serveur"""
    total_videos = sum(len(room['queue']) for room in rooms.values())
    total_files = len(video_files)
    total_size = sum(os.path.getsize(info['path']) for info in video_files.values() if os.path.exists(info['path']))
    
    return jsonify({
        'rooms': len(rooms),
        'total_videos_queued': total_videos,
        'stored_files': total_files,
        'storage_used_mb': round(total_size / (1024 * 1024), 2)
    }), 200

# ==================== WebSocket Server ====================

async def broadcast_to_room(room_id, message):
    """Envoie un message à tous les clients d'une room"""
    if room_id not in rooms:
        return
    
    message_json = json.dumps(message)
    disconnected = set()
    
    for client in rooms[room_id]['clients']:
        try:
            await client.send(message_json)
        except:
            disconnected.add(client)
    
    rooms[room_id]['clients'] -= disconnected

async def websocket_handler(websocket, path):
    room_id = None
    print(f"✅ Client WebSocket connecté")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get('action')
                
                if action == 'join':
                    room_id = data.get('room_id', 'default')
                    
                    if room_id not in rooms:
                        rooms[room_id] = {'clients': set(), 'queue': []}
                    
                    rooms[room_id]['clients'].add(websocket)
                    print(f"✅ Client ajouté à '{room_id}' ({len(rooms[room_id]['clients'])} total)")
                    
                    await websocket.send(json.dumps({
                        'action': 'sync',
                        'queue': rooms[room_id]['queue'],
                        'user_count': len(rooms[room_id]['clients'])
                    }))
                
                elif action == 'skip':
                    if room_id and room_id in rooms:
                        if rooms[room_id]['queue']:
                            skipped_video = rooms[room_id]['queue'].pop(0)
                            mark_video_played(skipped_video.get('url'), room_id)
                        
                        await broadcast_to_room(room_id, {
                            'action': 'video_skipped',
                            'queue': rooms[room_id]['queue']
                        })
                
                elif action == 'clear_all':
                    if room_id and room_id in rooms:
                        print(f"🗑️ Clear all pour '{room_id}'")
                        
                        for video in rooms[room_id]['queue']:
                            mark_video_played(video.get('url'), room_id)
                        
                        rooms[room_id]['queue'] = []
                        
                        await broadcast_to_room(room_id, {
                            'action': 'clear_all',
                            'queue': []
                        })
                
                elif action == 'video_finished':
                    if room_id and room_id in rooms and rooms[room_id]['queue']:
                        finished_video = rooms[room_id]['queue'].pop(0)
                        mark_video_played(finished_video.get('url'), room_id)
                        print(f"✅ Vidéo terminée et retirée de '{room_id}'")
                        
                        await broadcast_to_room(room_id, {
                            'action': 'queue_updated',
                            'queue': rooms[room_id]['queue']
                        })
            
            except json.JSONDecodeError as e:
                print(f"❌ Erreur JSON: {e}")
            except Exception as e:
                print(f"❌ Erreur handler: {e}")
    
    except websockets.exceptions.ConnectionClosed:
        print(f"🔌 Connexion WebSocket fermée")
    finally:
        if room_id and room_id in rooms:
            rooms[room_id]['clients'].discard(websocket)
            print(f"🧹 Client retiré de '{room_id}'")

async def start_websocket_server():
    print("🚀 Démarrage WebSocket sur ws://0.0.0.0:8765")
    async with websockets.serve(websocket_handler, "0.0.0.0", 8765):
        print("✅ Serveur WebSocket prêt !")
        await asyncio.Future()

def run_websocket_server():
    asyncio.run(start_websocket_server())

def cleanup_loop():
    """Boucle de nettoyage périodique"""
    while True:
        time.sleep(60)
        check_video_cleanup()

# ==================== Démarrage ====================

if __name__ == '__main__':
    ws_thread = Thread(target=run_websocket_server, daemon=True)
    ws_thread.start()
    
    cleanup_thread = Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    
    print("🌐 Serveur Flask sur http://0.0.0.0:5000")
    print("📡 Serveur WebSocket sur ws://0.0.0.0:8765")
    print("🧹 Nettoyage automatique activé (toutes les 60s)")
    
    app.run(host='0.0.0.0', port=5000, debug=False)