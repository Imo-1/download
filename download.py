#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# MAKE BY T.ME/REDX_64

import os
import sys
import re
import json
import subprocess
import time
import threading
import queue
import socket
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import uuid
import requests
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Telegram Config
BOT_TOKEN = "ENTER BOT TOKEN "
CHAT_ID = "ENTER CHATID NUMBER"

# Custom Server URL
SERVER_NAME = "redx-downloader"
CUSTOM_URL = f"http://{SERVER_NAME}.local:5000"

# Proxy APIs for Instagram
PROXY_APIS = [
    "https://api.snapsave.app/instagram/dl?url={url}",
    "https://api.qewertyy.dev/download/instagram?url={url}",
    "https://instagram-downloader-download-instagram-videos-stories.p.rapidapi.com/index?url={url}",
    "https://api.instagramsaver.com/api/ig/url?url={url}",
    "https://api.instagramsave.com/api/instagram/post?url={url}",
    "https://www.instagramsave.com/download.php?url={url}",
    "https://igram.io/api/convert?url={url}",
    "https://api.instadownloader.org/api/download?url={url}",
]

# API Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.instagram.com/',
    'Origin': 'https://www.instagram.com',
}

# Global download tracking
download_tasks = {}
download_queue = queue.Queue()
active_downloads = {}
console_logs = []

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def add_console_log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    console_logs.append(log_entry)
    if len(console_logs) > 50:
        console_logs.pop(0)
    return log_entry

class RedXDownloader:
    def __init__(self):
        # استخدام مجلد مؤقت آمن للتشغيل السحابي إذا لم يتوفر مسار التخزين الداخلي
        self.downloads_dir = "/tmp/RedX_Downloads" if not os.path.exists("/sdcard") else "/sdcard/Download/RedX_Downloads"
        if not os.path.exists(self.downloads_dir):
            try:
                os.makedirs(self.downloads_dir)
            except:
                self.downloads_dir = "./downloads"
                os.makedirs(self.downloads_dir, exist_ok=True)
        
        print(f"📁 Downloads Directory: {self.downloads_dir}")
        add_console_log(f"📁 Downloads Directory: {self.downloads_dir}")
        
        self.local_ip = get_local_ip()
        self.server_url = f"http://{self.local_ip}:5000"
        
        self.worker_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.worker_thread.start()
    
    def _download_worker(self):
        while True:
            try:
                task = download_queue.get()
                if task is None:
                    break
                
                task_id, url, quality, format_type = task
                
                try:
                    if "instagram.com" in url.lower():
                        platform = "instagram"
                        add_console_log(f"🔍 Detected Instagram: {url[:50]}...")
                        result = self._download_instagram_with_proxy(task_id, url)
                    elif "youtube.com" in url.lower() or "youtu.be" in url.lower():
                        platform = "youtube"
                        add_console_log(f"🔍 Detected YouTube: {url[:50]}...")
                        result = self._download_youtube_with_ytdlp(task_id, url, quality, format_type)
                    elif "tiktok.com" in url.lower():
                        platform = "tiktok"
                        add_console_log(f"🔍 Detected TikTok: {url[:50]}...")
                        result = self._download_tiktok_with_ytdlp(task_id, url)
                    elif "facebook.com" in url.lower() or "fb.watch" in url.lower():
                        platform = "facebook"
                        add_console_log(f"🔍 Detected Facebook: {url[:50]}...")
                        result = self._download_facebook_with_ytdlp(task_id, url)
                    else:
                        platform = "other"
                        add_console_log(f"🔍 Detected Other: {url[:50]}...")
                        result = self._download_generic_with_ytdlp(task_id, url, quality, format_type)
                    
                    result['status'] = 'completed' if result.get('success') else 'error'
                    download_tasks[task_id] = result
                    
                    if result.get('success'):
                        active_downloads[task_id] = {
                            'filename': result['filename'],
                            'size': result['size'],
                            'size_mb': result['size_mb'],
                            'timestamp': datetime.now().strftime("%H:%M:%S"),
                            'platform': platform,
                            'status': 'completed'
                        }
                        success_msg = f"✅ {platform.upper()} DOWNLOAD SUCCESS: {result['filename']}"
                        print(success_msg)
                        add_console_log(success_msg)
                    else:
                        error_msg = f"❌ {platform.upper()} DOWNLOAD FAILED: {result.get('error')}"
                        print(error_msg)
                        add_console_log(error_msg)
                
                except Exception as e:
                    error_msg = str(e)
                    print(f"⚠️ Task error: {error_msg}")
                    add_console_log(f"⚠️ Task error: {error_msg}")
                    download_tasks[task_id] = {'success': False, 'status': 'error', 'error': error_msg}
                
                finally:
                    download_queue.task_done()
                    
            except Exception as e:
                error_msg = f"⚠️ Worker error: {e}"
                print(error_msg)
                add_console_log(error_msg)
                time.sleep(2)
    
    def _download_instagram_with_proxy(self, task_id, url):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"RedX_Instagram_{timestamp}.mp4"
            output_path = os.path.join(self.downloads_dir, filename)
            clean_url = url.split('?')[0]
            
            for i, api_template in enumerate(PROXY_APIS):
                try:
                    api_url = api_template.format(url=clean_url)
                    response = requests.get(api_url, headers=HEADERS, timeout=15)
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '').lower()
                        if 'json' in content_type:
                            data = response.json()
                            video_url = self._extract_video_url_from_json(data)
                            if video_url:
                                return self._download_video_from_url(task_id, video_url, output_path, "instagram", "proxy_api")
                except:
                    continue
            return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'instagram')
        except Exception as e:
            return {'success': False, 'error': f'Instagram proxy error: {str(e)}', 'platform': 'instagram'}
    
    def _extract_video_url_from_json(self, data):
        try:
            if isinstance(data, dict):
                for key in ['url', 'video_url', 'download_url', 'media', 'link', 'video', 'hd', 'sd']:
                    if key in data:
                        val = data[key]
                        if isinstance(val, str) and 'http' in val:
                            return val
                        elif isinstance(val, dict) and 'url' in val:
                            return val['url']
            return None
        except:
            return None
    
    def _download_video_from_url(self, task_id, video_url, output_path, platform, method):
        try:
            response = requests.get(video_url, headers=HEADERS, timeout=30, stream=True)
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                if os.path.exists(output_path):
                    size = os.path.getsize(output_path)
                    if size > 1024:
                        return {
                            'success': True, 'filename': os.path.basename(output_path),
                            'filepath': output_path, 'size': size,
                            'size_mb': round(size / (1024 * 1024), 2),
                            'platform': platform, 'method': method
                        }
            return {'success': False, 'error': 'Failed to download video'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _download_youtube_with_ytdlp(self, task_id, url, quality, format_type):
        return self._download_with_ytdlp(task_id, url, quality, format_type, 'youtube')

    def _download_tiktok_with_ytdlp(self, task_id, url):
        return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'tiktok')

    def _download_facebook_with_ytdlp(self, task_id, url):
        return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'facebook')

    def _download_generic_with_ytdlp(self, task_id, url, quality, format_type):
        return self._download_with_ytdlp(task_id, url, quality, format_type, 'other')

    def _download_with_ytdlp(self, task_id, url, quality='best', format_type='mp4', platform='unknown'):
        try:
            import shutil
            ytdlp_bin = shutil.which('yt-dlp')
            if not ytdlp_bin:
                return {'success': False, 'error': 'yt-dlp not installed'}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"RedX_{platform}_{timestamp}"
            output_template = os.path.join(self.downloads_dir, base_name + '.%(ext)s')

            cmd = [ytdlp_bin, '--no-warnings', '-o', output_template, url]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            process.wait(timeout=300)

            candidates = [os.path.join(self.downloads_dir, f) for f in os.listdir(self.downloads_dir) if f.startswith(base_name) and not f.endswith(('.part', '.ytdl'))]
            if not candidates:
                return {'success': False, 'error': 'No output file created'}

            actual_file = max(candidates, key=os.path.getmtime)
            size = os.path.getsize(actual_file)
            return {
                'success': True, 'filename': os.path.basename(actual_file),
                'filepath': actual_file, 'size': size,
                'size_mb': round(size / (1024 * 1024), 2), 'platform': platform
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def queue_download(self, url, quality='best', format_type='mp4'):
        task_id = str(uuid.uuid4())[:8]
        download_queue.put((task_id, url, quality, format_type))
        return task_id

downloader = RedXDownloader()

@app.route('/')
def index():
    return '''<!DOCTYPE html><html><head><title>REDX DOWNLOADER</title></head><body style="background:#111;color:#fff;text-align:center;padding:50px;"><h1>🔥 REDX VIDEO DOWNLOADER</h1><p>Server is running successfully!</p></body></html>'''

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})
    task_id = downloader.queue_download(url)
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/progress/<task_id>')
def get_progress(task_id):
    return jsonify(download_tasks.get(task_id, {'status': 'queued'}))

@app.route('/download_file/<filename>')
def download_file(filename):
    filepath = os.path.join(downloader.downloads_dir, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
