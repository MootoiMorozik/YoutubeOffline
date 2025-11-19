from flask import Flask, render_template, request, jsonify, send_file, redirect
import yt_dlp, json, tempfile, os
from pathlib import Path
import logging
import socket
import requests
from urllib.parse import urlparse

app = Flask(__name__)
DATA = "data.json"
VIDEOS_DIR = "videos"
THUMBS_DIR = "thumbs"

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)

logging.getLogger('yt_dlp').setLevel(logging.ERROR)

def load_db():
    if not os.path.exists(DATA):
        return []
    with open(DATA, "r", encoding="utf8") as f:
        return json.load(f)

def save_db(videos):
    with open(DATA, "w", encoding="utf8") as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)

def download_thumbnail(url, video_id):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            parsed_url = urlparse(url)
            ext = '.jpg'  # по умолчанию jpg
            if '.webp' in parsed_url.path:
                ext = '.webp'
            elif '.png' in parsed_url.path:
                ext = '.png'
            
            filename = f"{video_id}{ext}"
            filepath = os.path.join(THUMBS_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return filename
    except Exception as e:
        print(f"Ошибка загрузки превью: {e}")
    
    return None

@app.route("/")
def index():
    videos = load_db()
    return render_template("index.html", videos=videos)

@app.route("/add", methods=["POST"])
def add():
    url = request.form.get("url").strip()

    if not url:
        return redirect("/")

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        videos = load_db()
        
        thumbnail_filename = None
        if info.get('thumbnail'):
            thumbnail_filename = download_thumbnail(info['thumbnail'], info['id'])
        
        entry = {
            "id": info["id"],
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "thumbnail_local": thumbnail_filename,
            "url": url,
            "duration": info.get("duration"),
        }
        videos.append(entry)
        save_db(videos)

    except Exception as e:
        print("YT-DLP ERROR:", e)

    return redirect("/")

@app.route("/video/<vid>")
def watch(vid):
    videos = load_db()
    video = next((x for x in videos if x["id"] == vid), None)

    if not video:
        return "Video not found", 404

    video_file = None
    for file in os.listdir(VIDEOS_DIR):
        if vid in file and file.endswith('.mp4'):
            video_file = file
            break

    return render_template("watch.html", video=video, video_file=video_file)


@app.route("/download/mp4", methods=["POST"])
def dl_mp4():
    url = request.json.get("url")
    quality = request.json.get("quality", "720")
    
    quality_map = {
        "144": "bestvideo[height<=144]+bestaudio/best[height<=144]",
        "360": "bestvideo[height<=360]+bestaudio/best[height<=360]", 
        "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
        "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
        "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    }
    
    fmt = quality_map.get(quality, "bestvideo+bestaudio/best")

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        
        video_id = info["id"]
        safe_title = "".join(c for c in info.get('title', 'video') if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_title}_{video_id}.mp4"
        filepath = os.path.join(VIDEOS_DIR, filename)

        if os.path.exists(filepath):
            return jsonify({
                "success": True,
                "message": "Видео уже скачано",
                "filename": filename
            })

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": filepath,
            "format": fmt,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return jsonify({
            "success": True,
            "message": "Видео успешно скачано",
            "filename": filename
        })
        
    except Exception as e:
        print(f"Ошибка скачивания: {e}")
        return jsonify({
            "success": False,
            "message": f"Ошибка скачивания: {str(e)}"
        }), 500


@app.route("/videos/<filename>")
def stream_video(filename):
    return send_file(os.path.join(VIDEOS_DIR, filename))

@app.route("/thumbs/<filename>")
def stream_thumb(filename):
    return send_file(os.path.join(THUMBS_DIR, filename))

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

if __name__ == "__main__":
    host = get_ip_address()
    port = 5000
    
    print("=" * 50)
    print("YouTube Downloader Server")
    print("=" * 50)
    print(f"Локальный доступ: http://localhost:{port}")
    print(f"Сеть Wi-Fi: http://{host}:{port}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=port, debug=True)