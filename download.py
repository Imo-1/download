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
        # مسار مؤقت آمن يمنع خطأ الصلاحيات على السيرفر السحابي ويحافظ على توافق أندرويد
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
                        value = data[key]
                        if isinstance(value, str) and 'http' in value:
                            return value
                        elif isinstance(value, dict) and 'url' in value:
                            return value['url']
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

    def _download_youtube_with_ytdlp(self, task_id, url, quality='best', format_type='mp4'):
        return self._download_with_ytdlp(task_id, url, quality, format_type, 'youtube')
    
    def _download_tiktok_with_ytdlp(self, task_id, url):
        return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'tiktok')
    
    def _download_facebook_with_ytdlp(self, task_id, url):
        return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'facebook')
    
    def _download_generic_with_ytdlp(self, task_id, url, quality='best', format_type='mp4'):
        return self._download_with_ytdlp(task_id, url, quality, format_type, 'other')
    
    def _download_with_ytdlp(self, task_id, url, quality='best', format_type='mp4', platform='unknown'):
        try:
            import shutil
            ytdlp_bin = shutil.which('yt-dlp')
            if not ytdlp_bin:
                return {'success': False, 'status': 'error', 'error': 'yt-dlp is not installed', 'platform': platform}

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_id = str(uuid.uuid4())[:6]
            base_name = f"RedX_{platform}_{timestamp}_{random_id}"
            output_template = os.path.join(self.downloads_dir, base_name + '.%(ext)s')

            # الحل النهائي: استخدام صيغة مدمجة وجاهزة (-f 'bv*+ba/b' أو 'best') تتجاوز حاجة السيرفر إلى برنامج ffmpeg الخارجي
            cmd = [
                ytdlp_bin, '-f', 'best',
                '--no-warnings', '--no-playlist',
                '-o', output_template, url
            ]

            add_console_log(f"🚀 {platform.upper()} Download starting with yt-dlp...")
            download_tasks[task_id] = {'status': 'downloading', 'progress': '5%', 'current_line': f'Starting {platform} download...'}

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
            
            last_lines = []
            for line in process.stdout:
                line = line.strip()
                if line:
                    last_lines.append(line)
                    if '[download]' in line and '%' in line:
                        match = re.search(r'(\d+(?:\.\d+)?)%', line)
                        if match:
                            download_tasks[task_id] = {'status': 'downloading', 'progress': match.group(1) + '%', 'current_line': line}

            return_code = process.wait(timeout=300)
            if return_code != 0:
                details = ' | '.join(last_lines[-3:]) or f'yt-dlp exited with code {return_code}'
                return {'success': False, 'status': 'error', 'error': details, 'platform': platform}

            candidates = [os.path.join(self.downloads_dir, f) for f in os.listdir(self.downloads_dir) if f.startswith(base_name) and not f.endswith(('.part', '.ytdl'))]
            if not candidates:
                return {'success': False, 'status': 'error', 'error': 'No output file created', 'platform': platform}

            actual_file = max(candidates, key=os.path.getmtime)
            size = os.path.getsize(actual_file)
            if size <= 1024:
                return {'success': False, 'status': 'error', 'error': 'Downloaded file is too small', 'platform': platform}

            return {
                'success': True, 'status': 'completed', 'filename': os.path.basename(actual_file),
                'filepath': actual_file, 'size': size, 'size_mb': round(size / (1024 * 1024), 2),
                'platform': platform, 'quality': quality, 'format': format_type
            }
        except Exception as e:
            return {'success': False, 'status': 'error', 'error': str(e), 'platform': platform}

    def queue_download(self, url, quality='best', format_type='mp4'):
        task_id = str(uuid.uuid4())[:8]
        download_queue.put((task_id, url, quality, format_type))
        return task_id

downloader = RedXDownloader()

@app.route('/')
def index():
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 REDX VIDEO DOWNLOADER</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Rajdhani', sans-serif;
            background: linear-gradient(135deg, #000000 0%, #1a0000 25%, #2a0000 50%, #1a0000 75%, #000000 100%);
            color: #ffffff; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 20px;
        }
        .container {
            width: 100%; max-width: 800px; background: rgba(20, 0, 0, 0.95);
            border-radius: 20px; padding: 30px; box-shadow: 0 20px 40px rgba(255, 0, 0, 0.3);
            border: 2px solid rgba(255, 0, 0, 0.5);
        }
        .header { text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid rgba(255, 0, 0, 0.5); }
        .title {
            font-family: 'Orbitron', monospace; font-size: 32px; font-weight: 900;
            background: linear-gradient(45deg, #ff0000, #ff4444, #ff0000);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px;
        }
        .subtitle { color: #ff8888; font-size: 14px; }
        .url-input {
            width: 100%; background: rgba(255, 255, 255, 0.1); border: 2px solid rgba(255, 0, 0, 0.5);
            border-radius: 10px; padding: 18px; font-size: 16px; color: white; margin-bottom: 20px; font-family: 'Rajdhani', sans-serif;
        }
        .url-input:focus { outline: none; border-color: #ff4444; box-shadow: 0 0 15px rgba(255, 0, 0, 0.5); }
        .download-btn {
            width: 100%; background: linear-gradient(135deg, #ff0000, #cc0000); border: none;
            border-radius: 10px; padding: 20px; color: white; font-family: 'Orbitron', monospace;
            font-size: 18px; font-weight: bold; cursor: pointer; margin: 20px 0; box-shadow: 0 8px 25px rgba(255, 0, 0, 0.4);
        }
        .download-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .status-message { background: rgba(255, 0, 0, 0.1); border-radius: 10px; padding: 15px; margin: 15px 0; text-align: center; display: none; border: 1px solid rgba(255, 0, 0, 0.3); }
        .downloads-list { margin: 25px 0; max-height: 400px; overflow-y: auto; }
        .download-item { background: rgba(255, 0, 0, 0.05); border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 4px solid #ff0000; }
        .download-filename { font-family: 'Orbitron', monospace; color: #ff4444; font-size: 14px; margin-bottom: 5px; word-break: break-all; }
        .download-button {
            background: linear-gradient(135deg, #ff0000, #cc0000); border: none; border-radius: 5px;
            padding: 8px 15px; color: white; cursor: pointer; font-size: 12px; margin-top: 10px; font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🔥 REDX VIDEO DOWNLOADER</h1>
            <p class="subtitle">YouTube • TikTok • Instagram • Facebook • 100+ Sites</p>
        </div>
        
        <div class="url-section">
            <input type="text" class="url-input" id="videoUrl" placeholder="🔗 Paste video URL here..." value="https://www.youtube.com/watch?v=dQw4w9WgXcQ">
        </div>
        
        <button class="download-btn" id="downloadBtn" onclick="startDownload()">🔥 START DOWNLOAD</button>
        
        <div class="status-message" id="successMessage"></div>
        <div class="status-message" id="errorMessage" style="color: #ff4444;"></div>
        
        <div class="downloads-list" id="downloadsList">
            <div style="color: #ff4444; margin-bottom: 15px; font-family: 'Orbitron', monospace;">📂 RECENT DOWNLOADS:</div>
            <div id="downloadItems"></div>
        </div>
    </div>
    
    <script>
        let currentTaskId = null;
        let pollInterval = null;
        
        function startDownload() {
            const url = document.getElementById('videoUrl').value.trim();
            if (!url) { alert('Please enter a video URL'); return; }
            
            const downloadBtn = document.getElementById('downloadBtn');
            downloadBtn.disabled = true;
            downloadBtn.innerHTML = '⏳ PROCESSING...';
            document.getElementById('successMessage').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';
            
            fetch('/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url, quality: 'best', format: 'mp4' })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    currentTaskId = data.task_id;
                    startPollingProgress();
                } else {
                    showError(data.error);
                }
            })
            .catch(err => {
                showError('Network error: ' + err);
            });
        }
        
        function startPollingProgress() {
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(() => {
                fetch('/progress/' + currentTaskId)
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'completed' || data.status === 'error') {
                        clearInterval(pollInterval);
                        handleDownloadComplete(data);
                    }
                });
            }, 1500);
        }
        
        function handleDownloadComplete(data) {
            const downloadBtn = document.getElementById('downloadBtn');
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = '🔥 START DOWNLOAD';
            
            if (data.success) {
                const successMsg = document.getElementById('successMessage');
                successMsg.innerHTML = `✅ DOWNLOAD SUCCESSFUL!<br>File: ${data.filename}<br>Size: ${data.size_mb} MB`;
                successMsg.style.display = 'block';
                addDownloadToList(data);
            } else {
                showError(data.error || 'Download failed');
            }
        }
        
        function showError(message) {
            const errorMsg = document.getElementById('errorMessage');
            errorMsg.innerHTML = `❌ ERROR: ${message}`;
            errorMsg.style.display = 'block';
            const downloadBtn = document.getElementById('downloadBtn');
            downloadBtn.disabled = false;
            downloadBtn.innerHTML = '🔥 START DOWNLOAD';
        }
        
        function addDownloadToList(data) {
            const downloadsList = document.getElementById('downloadItems');
            const item = document.createElement('div');
            item.className = 'download-item';
            item.innerHTML = `
                <div class="download-filename">📁 ${data.filename}</div>
                <div style="font-size: 12px; color: #ff8888; margin-top: 5px;">Size: ${data.size_mb} MB</div>
                <button class="download-button" onclick="window.open('/download_file/${encodeURIComponent(data.filename)}', '_blank')">⬇️ DOWNLOAD FILE</button>
            `;
            downloadsList.insertBefore(item, downloadsList.firstChild);
        }
    </script>
</body>
</html>
'''

@app.route('/download', methods=['POST'])
def start_download():
    try:
        data = request.json
        url = data.get('url')
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'})
        task_id = downloader.queue_download(url)
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/progress/<task_id>')
def get_progress(task_id):
    try:
        return jsonify(download_tasks.get(task_id, {'status': 'queued'}))
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/download_file/<filename>')
def download_file(filename):
    try:
        filepath = os.path.join(downloader.downloads_dir, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        return "File not found", 404
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
