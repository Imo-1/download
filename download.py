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
CUSTOM_URL = f"http://{SERVER_NAME}.local:5000"  # Change this to your custom URL

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
    """Get local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def add_console_log(message):
    """Add message to console log"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    console_logs.append(log_entry)
    if len(console_logs) > 50:
        console_logs.pop(0)
    return log_entry

class RedXDownloader:
    def __init__(self):
        # توافق تام: يستخدم مسار الأندرويد إن وجد، أو مجلد مؤقت آمن /tmp للسيرفرات السحابية
        self.downloads_dir = "/tmp/RedX_Downloads" if not os.path.exists("/sdcard") else "/sdcard/Download/RedX_Downloads"
        if not os.path.exists(self.downloads_dir):
            try:
                os.makedirs(self.downloads_dir)
            except:
                self.downloads_dir = "./downloads"
                os.makedirs(self.downloads_dir, exist_ok=True)
        
        print(f"📁 Downloads Directory: {self.downloads_dir}")
        add_console_log(f"📁 Downloads Directory: {self.downloads_dir}")
        
        # Get network info
        self.local_ip = get_local_ip()
        self.server_url = f"http://{self.local_ip}:5000"
        
        # Start download worker
        self.worker_thread = threading.Thread(target=self._download_worker, daemon=True)
        self.worker_thread.start()
    
    def _download_worker(self):
        """Background worker for downloads"""
        while True:
            try:
                task = download_queue.get()
                if task is None:
                    break
                
                task_id, url, quality, format_type = task
                
                try:
                    # Detect platform
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
                        # Store in active downloads
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
                        
                        # Send Telegram notification
                        if BOT_TOKEN and CHAT_ID:
                            self._send_telegram(f"""
✅ {platform.upper()} DOWNLOAD COMPLETED!
📁 File: {result['filename']}
📦 Size: {result['size_mb']} MB
⏰ Time: {datetime.now().strftime('%H:%M:%S')}
🔗 By: @REDX_64
                            """)
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
        """Download Instagram using Proxy APIs"""
        try:
            add_console_log(f"🚀 Starting Instagram download via Proxy API: {url[:50]}...")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"RedX_Instagram_{timestamp}.mp4"
            output_path = os.path.join(self.downloads_dir, filename)
            
            # Clean URL
            clean_url = url.split('?')[0]
            
            # Try different proxy APIs
            for i, api_template in enumerate(PROXY_APIS):
                try:
                    api_url = api_template.format(url=clean_url)
                    add_console_log(f"🌐 Trying API {i+1}: {api_url[:50]}...")
                    
                    # Update progress
                    download_tasks[task_id] = {
                        'status': 'downloading',
                        'progress': '10%',
                        'current_line': f'Connecting to API {i+1}...'
                    }
                    
                    # Make API request
                    response = requests.get(api_url, headers=HEADERS, timeout=15)
                    
                    if response.status_code == 200:
                        # Try to parse response
                        content_type = response.headers.get('content-type', '').lower()
                        
                        if 'json' in content_type:
                            data = response.json()
                            
                            # Extract video URL from response
                            video_url = self._extract_video_url_from_json(data)
                            
                            if video_url:
                                add_console_log(f"🎬 Found video URL: {video_url[:50]}...")
                                
                                # Download the video
                                return self._download_video_from_url(task_id, video_url, output_path, "instagram", "proxy_api")
                        
                        elif 'video' in content_type or 'mp4' in content_type:
                            # Direct video response
                            add_console_log("📹 Direct video response from API")
                            
                            # Download video
                            total_size = int(response.headers.get('content-length', 0))
                            downloaded = 0
                            
                            with open(output_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    if chunk:
                                        f.write(chunk)
                                        downloaded += len(chunk)
                                        
                                        # Update progress
                                        if total_size > 0:
                                            progress = 10 + (downloaded / total_size) * 80
                                            download_tasks[task_id] = {
                                                'status': 'downloading',
                                                'progress': f'{progress:.1f}%',
                                                'current_line': f'Downloading: {downloaded/(1024*1024):.1f} MB'
                                            }
                            
                            # Verify download
                            if os.path.exists(output_path):
                                size = os.path.getsize(output_path)
                                if size > 1024:
                                    size_mb = size / (1024 * 1024)
                                    
                                    download_tasks[task_id] = {
                                        'status': 'downloading',
                                        'progress': '100%',
                                        'current_line': 'Download complete!'
                                    }
                                    
                                    return {
                                        'success': True,
                                        'filename': filename,
                                        'filepath': output_path,
                                        'size': size,
                                        'size_mb': round(size_mb, 2),
                                        'platform': 'instagram',
                                        'method': 'direct_api'
                                    }
                
                except Exception as api_error:
                    add_console_log(f"⚠️ API error {i+1}: {api_error}")
                    continue
            
            # If all APIs fail, try yt-dlp as fallback
            add_console_log("🔄 Trying yt-dlp as fallback...")
            return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'instagram')
            
        except Exception as e:
            return {'success': False, 'error': f'Instagram proxy error: {str(e)}', 'platform': 'instagram'}
    
    def _extract_video_url_from_json(self, data):
        """Extract video URL from JSON response"""
        try:
            # Try different response formats
            if isinstance(data, dict):
                # Check common keys
                possible_keys = ['url', 'video_url', 'download_url', 'media', 'link', 'video', 'hd', 'sd']
                
                for key in possible_keys:
                    if key in data:
                        value = data[key]
                        
                        # If it's a string URL
                        if isinstance(value, str) and ('http' in value or 'mp4' in value):
                            return value
                        
                        # If it's a dict with url
                        elif isinstance(value, dict):
                            if 'url' in value:
                                return value['url']
                            elif 'video_url' in value:
                                return value['video_url']
                        
                        # If it's a list
                        elif isinstance(value, list) and len(value) > 0:
                            if isinstance(value[0], dict):
                                if 'url' in value[0]:
                                    return value[0]['url']
                                elif 'video_url' in value[0]:
                                    return value[0]['video_url']
            
            return None
            
        except Exception as e:
            add_console_log(f"⚠️ URL extraction error: {e}")
            return None
    
    def _download_video_from_url(self, task_id, video_url, output_path, platform, method):
        """Download video from direct URL"""
        try:
            add_console_log(f"📥 Downloading from URL: {video_url[:50]}...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Referer': 'https://www.instagram.com/',
            }
            
            # Update progress
            download_tasks[task_id] = {
                'status': 'downloading',
                'progress': '20%',
                'current_line': 'Starting video download...'
            }
            
            # Download video
            response = requests.get(video_url, headers=headers, timeout=30, stream=True)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Update progress
                            if total_size > 0:
                                progress = 20 + (downloaded / total_size) * 70
                                download_tasks[task_id] = {
                                    'status': 'downloading',
                                    'progress': f'{progress:.1f}%',
                                    'current_line': f'Downloading: {downloaded/(1024*1024):.1f} MB'
                                }
                
                # Verify download
                if os.path.exists(output_path):
                    size = os.path.getsize(output_path)
                    if size > 1024:
                        size_mb = size / (1024 * 1024)
                        
                        download_tasks[task_id] = {
                            'status': 'downloading',
                            'progress': '100%',
                            'current_line': 'Download complete!'
                        }
                        
                        return {
                            'success': True,
                            'filename': os.path.basename(output_path),
                            'filepath': output_path,
                            'size': size,
                            'size_mb': round(size_mb, 2),
                            'platform': platform,
                            'method': method
                        }
            
            return {'success': False, 'error': 'Failed to download video from URL', 'platform': platform}
            
        except Exception as e:
            return {'success': False, 'error': f'Video download error: {str(e)}', 'platform': platform}
    
    def _download_youtube_with_ytdlp(self, task_id, url, quality='best', format_type='mp4'):
        """Download YouTube videos"""
        return self._download_with_ytdlp(task_id, url, quality, format_type, 'youtube')
    
    def _download_tiktok_with_ytdlp(self, task_id, url):
        """Download TikTok videos"""
        return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'tiktok')
    
    def _download_facebook_with_ytdlp(self, task_id, url):
        """Download Facebook videos"""
        return self._download_with_ytdlp(task_id, url, 'best', 'mp4', 'facebook')
    
    def _download_generic_with_ytdlp(self, task_id, url, quality='best', format_type='mp4'):
        """Download generic videos"""
        return self._download_with_ytdlp(task_id, url, quality, format_type, 'other')
    
    def _download_with_ytdlp(self, task_id, url, quality='best', format_type='mp4', platform='unknown'):
        """Generic download using yt-dlp with reliable executable/file detection."""
        try:
            import shutil

            ytdlp_bin = shutil.which('yt-dlp')
            if not ytdlp_bin:
                return {
                    'success': False,
                    'status': 'error',
                    'error': 'yt-dlp is not installed or not available in PATH. Run: pip install -U yt-dlp',
                    'platform': platform
                }

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            random_id = str(uuid.uuid4())[:6]
            base_name = f"RedX_{platform}_{timestamp}_{random_id}"
            output_template = os.path.join(self.downloads_dir, base_name + '.%(ext)s')

            if format_type == 'mp3':
                if not shutil.which('ffmpeg'):
                    return {
                        'success': False, 'status': 'error',
                        'error': 'FFmpeg is required for MP3 conversion. In Termux run: pkg install ffmpeg',
                        'platform': platform
                    }
                cmd = [
                    ytdlp_bin, '-x', '--audio-format', 'mp3', '--audio-quality', '0',
                    '--no-warnings', '--newline', '--progress', '--no-playlist',
                    '-o', output_template, url
                ]
            else:
                # استخدام صيغة جاهزة ومتوافقة تماماً مع السيرفرات السحابية لتجنب أخطاء دمج FFmpeg
                cmd = [
                    ytdlp_bin, '-f', 'best',
                    '--no-warnings', '--newline', '--progress', '--no-playlist',
                    '-o', output_template, url
                ]

            add_console_log(f"🚀 {platform.upper()} Download starting with yt-dlp...")
            download_tasks[task_id] = {
                'status': 'downloading', 'progress': '5%',
                'current_line': f'Starting {platform} download...'
            }

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace', bufsize=1
            )

            last_lines = []
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                last_lines.append(line)
                last_lines = last_lines[-8:]
                if '[download]' in line and '%' in line:
                    match = re.search(r'(\d+(?:\.\d+)?)%', line)
                    if match:
                        progress = match.group(1) + '%'
                        download_tasks[task_id] = {
                            'status': 'downloading', 'progress': progress,
                            'current_line': f'{platform}: {line}'
                        }
                add_console_log(f"📥 {platform}: {line}")

            return_code = process.wait(timeout=300)
            if return_code != 0:
                details = ' | '.join(last_lines[-4:]) or f'yt-dlp exited with code {return_code}'
                return {'success': False, 'status': 'error', 'error': details, 'platform': platform}

            # Only accept files belonging to this task. Never reuse an older download.
            candidates = []
            for f in os.listdir(self.downloads_dir):
                if f.startswith(base_name) and not f.endswith(('.part', '.ytdl')):
                    path = os.path.join(self.downloads_dir, f)
                    if os.path.isfile(path):
                        candidates.append(path)

            if not candidates:
                return {'success': False, 'status': 'error', 'error': 'yt-dlp finished but no output file was created', 'platform': platform}

            actual_file = max(candidates, key=os.path.getmtime)
            size = os.path.getsize(actual_file)
            if size <= 1024:
                return {'success': False, 'status': 'error', 'error': 'Downloaded file is too small', 'platform': platform}

            filename = os.path.basename(actual_file)
            size_mb = size / (1024 * 1024)
            return {
                'success': True, 'status': 'completed', 'filename': filename,
                'filepath': actual_file, 'size': size, 'size_mb': round(size_mb, 2),
                'platform': platform, 'quality': quality, 'format': format_type
            }

        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except Exception:
                pass
            return {'success': False, 'status': 'error', 'error': 'Download timed out after 300 seconds', 'platform': platform}
        except Exception as e:
            return {'success': False, 'status': 'error', 'error': f'Error: {str(e)}', 'platform': platform}

    def _send_telegram(self, msg):
        """Send Telegram notification"""
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
            requests.post(url, data=data, timeout=5)
            return True
        except:
            return False
    
    def queue_download(self, url, quality='best', format_type='mp4'):
        """Queue a download"""
        task_id = str(uuid.uuid4())[:8]
        
        # Detect platform
        if "instagram.com" in url.lower():
            platform = "instagram"
        elif "youtube.com" in url.lower() or "youtu.be" in url.lower():
            platform = "youtube"
        elif "tiktok.com" in url.lower():
            platform = "tiktok"
        elif "facebook.com" in url.lower() or "fb.watch" in url.lower():
            platform = "facebook"
        else:
            platform = "other"
        
        download_tasks[task_id] = {
            'status': 'queued',
            'progress': '0%',
            'message': f'Queued for {platform}...',
            'platform': platform
        }
        
        add_console_log(f"📋 Task {task_id} queued: {platform} - {url[:50]}...")
        
        download_queue.put((task_id, url, quality, format_type))
        
        return task_id
    
    def get_active_downloads(self):
        """Get list of downloads"""
        return active_downloads

# Initialize downloader
downloader = RedXDownloader()

@app.route('/')
def index():
    """Main page - REDX BRANDED"""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔥 REDX VIDEO DOWNLOADER</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap');
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Rajdhani', sans-serif;
            background: linear-gradient(135deg, #000000 0%, #1a0000 25%, #2a0000 50%, #1a0000 75%, #000000 100%);
            color: #ffffff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            overflow-x: hidden;
        }
        
        .container {
            width: 100%;
            max-width: 800px;
            background: rgba(20, 0, 0, 0.95);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(255, 0, 0, 0.3);
            border: 2px solid rgba(255, 0, 0, 0.5);
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid rgba(255, 0, 0, 0.5);
        }
        
        .title {
            font-family: 'Orbitron', monospace;
            font-size: 32px;
            font-weight: 900;
            background: linear-gradient(45deg, #ff0000, #ff4444, #ff0000);
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
            text-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
        }
        
        .subtitle {
            color: #ff8888;
            font-size: 14px;
        }
        
        .brand {
            color: #ff0000;
            font-family: 'Orbitron', monospace;
            font-size: 12px;
            margin-top: 5px;
            letter-spacing: 2px;
        }
        
        .url-section {
            margin: 25px 0;
        }
        
        .url-input {
            width: 100%;
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 0, 0, 0.5);
            border-radius: 10px;
            padding: 18px;
            font-size: 16px;
            color: white;
            margin-bottom: 20px;
            font-family: 'Rajdhani', sans-serif;
        }
        
        .url-input:focus {
            outline: none;
            border-color: #ff4444;
            box-shadow: 0 0 15px rgba(255, 0, 0, 0.5);
        }
        
        .quality-section {
            margin: 20px 0;
        }
        
        .quality-buttons {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin: 15px 0;
        }
        
        .quality-btn {
            background: rgba(255, 0, 0, 0.1);
            border: 2px solid #550000;
            border-radius: 8px;
            padding: 15px;
            color: white;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .quality-btn:hover {
            border-color: #ff0000;
            transform: translateY(-2px);
            background: rgba(255, 0, 0, 0.2);
        }
        
        .quality-btn.active {
            background: rgba(255, 0, 0, 0.3);
            border-color: #ff0000;
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
        }
        
        .download-btn {
            width: 100%;
            background: linear-gradient(135deg, #ff0000, #cc0000, #ff0000);
            background-size: 200% 200%;
            animation: gradient 2s ease infinite;
            border: none;
            border-radius: 10px;
            padding: 20px;
            color: white;
            font-family: 'Orbitron', monospace;
            font-size: 18px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s;
            margin: 25px 0;
            box-shadow: 0 8px 25px rgba(255, 0, 0, 0.4);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        @keyframes gradient {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        .download-btn:hover:not(:disabled) {
            transform: translateY(-3px);
            box-shadow: 0 12px 35px rgba(255, 0, 0, 0.6);
        }
        
        .download-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .real-progress-section {
            margin: 25px 0;
            display: none;
        }
        
        .progress-container {
            background: rgba(255, 0, 0, 0.1);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            border: 1px solid rgba(255, 0, 0, 0.3);
        }
        
        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
        }
        
        .progress-title {
            color: #ff4444;
            font-family: 'Orbitron', monospace;
            font-size: 16px;
        }
        
        .progress-percent {
            color: #ff0000;
            font-family: 'Orbitron', monospace;
            font-size: 18px;
            font-weight: bold;
            text-shadow: 0 0 5px rgba(255, 0, 0, 0.5);
        }
        
        .progress-bar {
            height: 12px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            overflow: hidden;
            margin-bottom: 15px;
            border: 1px solid rgba(255, 0, 0, 0.3);
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #ff0000, #ff4444);
            border-radius: 6px;
            width: 0%;
            transition: width 0.5s;
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
        }
        
        .status-message {
            background: rgba(255, 0, 0, 0.1);
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            text-align: center;
            display: none;
            border: 1px solid rgba(255, 0, 0, 0.3);
        }
        
        .status-success {
            background: rgba(0, 255, 0, 0.1);
            border: 1px solid rgba(0, 255, 0, 0.5);
            color: #00ff00;
        }
        
        .status-error {
            background: rgba(255, 0, 0, 0.2);
            border: 1px solid rgba(255, 0, 0, 0.5);
            color: #ff4444;
        }
        
        .downloads-list {
            margin: 25px 0;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .download-item {
            background: rgba(255, 0, 0, 0.05);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            border-left: 4px solid #ff0000;
        }
        
        .download-filename {
            font-family: 'Orbitron', monospace;
            color: #ff4444;
            font-size: 14px;
            margin-bottom: 5px;
            word-break: break-all;
        }
        
        .download-info {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #ff8888;
        }
        
        .download-button {
            background: linear-gradient(135deg, #ff0000, #cc0000);
            border: none;
            border-radius: 5px;
            padding: 8px 15px;
            color: white;
            cursor: pointer;
            font-size: 12px;
            margin-top: 10px;
            font-family: 'Rajdhani', sans-serif;
            font-weight: 600;
        }
        
        .download-button:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }
        
        .live-console {
            background: #000;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
            font-family: monospace;
            font-size: 12px;
            color: #ff4444;
            max-height: 200px;
            overflow-y: auto;
            display: none;
            border: 1px solid rgba(255, 0, 0, 0.5);
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.2);
        }
        
        .console-line {
            margin: 3px 0;
            padding: 3px 0;
            border-bottom: 1px solid rgba(255, 0, 0, 0.1);
            animation: fadeIn 0.3s;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 0, 0, 0.3);
        }
        
        .server-info {
            color: #ff8888;
            font-size: 12px;
            margin-bottom: 15px;
            font-family: monospace;
            background: rgba(255, 0, 0, 0.1);
            padding: 10px;
            border-radius: 5px;
            border: 1px solid rgba(255, 0, 0, 0.3);
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 20px;
                max-width: 95%;
            }
            
            .title {
                font-size: 24px;
            }
            
            .quality-buttons {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">🔥 REDX VIDEO DOWNLOADER</h1>
            <p class="subtitle">YouTube • Instagram • TikTok • Facebook • 100+ Sites</p>
            <p class="brand">MAKE BY T.ME/REDX_64</p>
        </div>
        
        <!-- URL Input -->
        <div class="url-section">
            <input type="text" class="url-input" id="videoUrl" 
                   placeholder="🔗 Paste video URL here (YouTube, Instagram, TikTok, etc.)" 
                   value="https://www.youtube.com/watch?v=dQw4w9WgXcQ">
            <div style="text-align: center; color: #ff8888; font-size: 12px; margin-top: 5px;">
                YouTube: 100% Working • Instagram: Proxy APIs • TikTok: 100% Working
            </div>
        </div>
        
        <!-- Quality Selection -->
        <div class="quality-section">
            <div style="color: #ff4444; margin-bottom: 10px; font-family: 'Orbitron', monospace;">
                SELECT QUALITY:
            </div>
            <div class="quality-buttons">
                <button class="quality-btn active" onclick="selectQuality('360p')">
                    📱 360p
                    <div style="font-size: 11px; color: #ff8888; margin-top: 5px;">Fast Download</div>
                </button>
                <button class="quality-btn" onclick="selectQuality('720p')">
                    📺 720p HD
                    <div style="font-size: 11px; color: #ff8888; margin-top: 5px;">Good Quality</div>
                </button>
                <button class="quality-btn" onclick="selectQuality('best')">
                    👑 BEST
                    <div style="font-size: 11px; color: #ff8888; margin-top: 5px;">Max Quality</div>
                </button>
            </div>
        </div>
        
        <!-- Download Button -->
        <button class="download-btn" id="downloadBtn" onclick="startDownload()">
            🔥 START DOWNLOAD
        </button>
        
        <!-- Real Progress Section -->
        <div class="real-progress-section" id="progressSection">
            <div class="progress-container">
                <div class="progress-header">
                    <div class="progress-title">DOWNLOAD PROGRESS</div>
                    <div class="progress-percent" id="progressPercent">0%</div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div style="text-align: center; color: #ff8888; font-size: 12px; margin-top: 10px;" id="progressStatus">
                    Initializing download...
                </div>
                
                <!-- Live Console -->
                <div class="live-console" id="liveConsole">
                    <div style="color: #ff0000; margin-bottom: 10px; font-family: 'Orbitron', monospace;">
                        🔥 REDX DOWNLOAD LOG:
                    </div>
                    <div id="consoleOutput"></div>
                </div>
                
                <button onclick="toggleConsole()" style="
                    background: rgba(255, 0, 0, 0.2);
                    border: 1px solid #ff4444;
                    color: #ff4444;
                    padding: 8px 15px;
                    border-radius: 5px;
                    cursor: pointer;
                    margin-top: 10px;
                    font-size: 12px;
                    font-family: 'Rajdhani', sans-serif;
                    font-weight: 600;
                ">
                    📜 SHOW/HIDE CONSOLE
                </button>
            </div>
        </div>
        
        <!-- Status Messages -->
        <div class="status-message" id="successMessage">
            ✅ DOWNLOAD SUCCESSFUL! Check your downloads folder.
        </div>
        
        <div class="status-message status-error" id="errorMessage">
            ❌ DOWNLOAD FAILED! Please check the URL and try again.
        </div>
        
        <!-- Downloads List -->
        <div class="downloads-list" id="downloadsList">
            <div style="color: #ff4444; margin-bottom: 15px; font-family: 'Orbitron', monospace;">
                📂 RECENT DOWNLOADS:
            </div>
            <div id="downloadItems">
                <!-- Downloads will be added here dynamically -->
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <div class="server-info" id="serverInfo">
                Server: Loading...
            </div>
            <div style="color: #ff8888; font-size: 11px;">
                🔥 POWERED BY REDX_64 • Telegram: @REDX_64
            </div>
            <div style="color: #ff8888; font-size: 10px; margin-top: 10px;">
                Supports: YouTube, Instagram, TikTok, Facebook, Twitter, Snapchat, Pinterest, Likee, OK.ru, Vimeo, Dailymotion, SoundCloud, Twitch, Reddit, LinkedIn, Imgur, Tumblr, Flickr, VK, Weibo, Bilibili, Douyin, Kwai, ShareChat, Moj, Josh, MX TakaTak, Roposo, Chingari, Mitron, Trell, Moj Lite, YouTube Shorts, Instagram Reels, Facebook Reels, Snapchat Spotlight, TikTok LIVE, YouTube LIVE, Facebook LIVE, Instagram LIVE, Twitch LIVE, Reddit LIVE, LinkedIn LIVE, Vimeo LIVE, Dailymotion LIVE, SoundCloud LIVE, Imgur LIVE, Tumblr LIVE, Flickr LIVE, VK LIVE, Weibo LIVE, Bilibili LIVE, Douyin LIVE, Kwai LIVE, ShareChat LIVE, Moj LIVE, Josh LIVE, MX TakaTak LIVE, Roposo LIVE, Chingari LIVE, Mitron LIVE, Trell LIVE, Moj Lite LIVE, YouTube Music, SoundCloud Music, Spotify, Deezer, Apple Music, Amazon Music, Google Play Music, Pandora, Tidal, Napster, iHeartRadio, Gaana, JioSaavn, Wynk Music, Hungama, Spotify Podcast, Google Podcasts, Apple Podcasts, Amazon Podcasts, iHeartRadio Podcasts, TuneIn, Stitcher, Pocket Casts, Castbox, Overcast, Player FM, Podcast Addict, Podcast Republic, AntennaPod, BeyondPod, DoggCatcher, Podkicker, Podbean, SoundCloud Go+, YouTube Premium, Netflix, Amazon Prime Video, Disney+, Hulu, HBO Max, Apple TV+, Paramount+, Peacock, Discovery+, ESPN+, Crunchyroll, Funimation, VRV, Shudder, BritBox, Acorn TV, Sundance Now, Mubi, Criterion Channel, Kanopy, Hoopla, Tubi, Pluto TV, Crackle, Popcornflix, Vudu, IMDb TV, Xumo, Sling TV, YouTube TV, Hulu + Live TV, FuboTV, AT&T TV Now, Philo, Vidgo, Locast, Frndly TV, and 1000+ more sites!
            </div>
        </div>
    </div>
    
    <script>
        let currentQuality = 'best';
        let currentTaskId = null;
        let pollInterval = null;
        let consoleVisible = false;
        
        function selectQuality(quality) {
            currentQuality = quality;
            
            // Update button states
            document.querySelectorAll('.quality-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.textContent.includes(quality)) {
                    btn.classList.add('active');
                }
            });
            
            addConsoleLog(`📊 Quality set to: ${quality}`);
        }
        
        function addConsoleLog(message) {
            const consoleOutput = document.getElementById('consoleOutput');
            const timestamp = new Date().toLocaleTimeString();
            const logEntry = document.createElement('div');
            logEntry.className = 'console-line';
            logEntry.innerHTML = `<span style="color: #ff8888">[${timestamp}]</span> ${message}`;
            consoleOutput.appendChild(logEntry);
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        }
        
        function toggleConsole() {
            const consoleElem = document.getElementById('liveConsole');
            consoleVisible = !consoleVisible;
            consoleElem.style.display = consoleVisible ? 'block' : 'none';
        }
        
        function startDownload() {
            const url = document.getElementById('videoUrl').value.trim();
            
            if (!url) {
                showError('Please enter a video URL');
                return;
            }
            
            if (!url.startsWith('http')) {
                showError('Please enter a valid URL starting with http:// or https://');
                return;
            }
            
            // Disable download button
            const downloadBtn = document.getElementById('downloadBtn');
            downloadBtn.disabled = true;
            downloadBtn.innerHTML = '⏳ PROCESSING...';
            
            // Show progress section
            document.getElementById('progressSection').style.display = 'block';
            document.getElementById('successMessage').style.display = 'none';
            document.getElementById('errorMessage').style.display = 'none';
            
            // Reset progress
            document.getElementById('progressPercent').textContent = '0%';
            document.getElementById('progressFill').style.width = '0%';
            document.getElementById('progressStatus').textContent = 'Starting download...';
            
            // Clear console
            document.getElementById('consoleOutput').innerHTML = '';
            addConsoleLog('🚀 Starting RedX Downloader...');
            addConsoleLog(`🔗 URL: ${url}`);
            addConsoleLog(`📊 Quality: ${currentQuality}`);
            addConsoleLog('⏳ Connecting to server...');
            
            // Start download
            fetch('/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    url: url,
                    quality: currentQuality,
                    format: 'mp4'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentTaskId = data.task_id;
                    addConsoleLog(`✅ Task created: ${currentTaskId}`);
                    addConsoleLog('📥 Download queued successfully');
                    
                    // Start polling progress
                    startPollingProgress();
                } else {
                    showError('Failed to start download: ' + data.error);
                    downloadBtn.disabled = false;
                    downloadBtn.innerHTML = '🔥 START DOWNLOAD';
                }
            })
            .catch(error => {
                showError('Network error: ' + error);
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '🔥 START DOWNLOAD';
            });
        }
        
        function startPollingProgress() {
            if (pollInterval) clearInterval(pollInterval);
            
            pollInterval = setInterval(() => {
                fetch('/progress/' + currentTaskId)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'completed' || data.status === 'error') {
                            clearInterval(pollInterval);
                            handleDownloadComplete(data);
                        } else {
                            updateProgress(data);
                        }
                    })
                    .catch(error => {
                        console.error('Polling error:', error);
                    });
            }, 1000);
        }
        
        function updateProgress(data) {
            const progressPercent = data.progress || '0%';
            const progressValue = parseFloat(progressPercent);
            
            document.getElementById('progressPercent').textContent = progressPercent;
            document.getElementById('progressFill').style.width = progressPercent;
            document.getElementById('progressStatus').textContent = data.current_line || 'Downloading...';
            
            // Update button
            const downloadBtn = document.getElementById('downloadBtn');
            downloadBtn.innerHTML = `🔥 DOWNLOADING ${progressPercent}`;
            
            // Add to console if new message
            if (data.current_line) {
                addConsoleLog(data.current_line);
            }
        }
        
        function handleDownloadComplete(data) {
            const downloadBtn = document.getElementById('downloadBtn');
            
            if (data.success) {
                // Success
                document.getElementById('progressPercent').textContent = '100%';
                document.getElementById('progressFill').style.width = '100%';
                document.getElementById('progressStatus').textContent = 'Download complete!';
                
                addConsoleLog(`✅ Download completed: ${data.filename}`);
                addConsoleLog(`📦 File size: ${data.size_mb} MB`);
                
                // Show success message
                const successMsg = document.getElementById('successMessage');
                successMsg.innerHTML = `✅ DOWNLOAD SUCCESSFUL!<br>File: ${data.filename}<br>Size: ${data.size_mb} MB`;
                successMsg.style.display = 'block';
                
                // Update downloads list
                addDownloadToList(data);
                
                // Update button
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '🔥 DOWNLOAD AGAIN';
                
                // Load console logs
                loadConsoleLogs();
                
            } else {
                // Error
                showError(data.error || 'Download failed');
                downloadBtn.disabled = false;
                downloadBtn.innerHTML = '🔥 TRY AGAIN';
            }
        }
        
        function showError(message) {
            const errorMsg = document.getElementById('errorMessage');
            errorMsg.innerHTML = `❌ ERROR: ${message}`;
            errorMsg.style.display = 'block';
            addConsoleLog(`❌ Error: ${message}`);
        }
        
        function addDownloadToList(data) {
            const downloadsList = document.getElementById('downloadItems');
            const downloadItem = document.createElement('div');
            downloadItem.className = 'download-item';
            
            const timestamp = new Date().toLocaleTimeString();
            
            downloadItem.innerHTML = `
                <div class="download-filename">📁 ${data.filename}</div>
                <div class="download-info">
                    <span>📦 ${data.size_mb} MB</span>
                    <span>🕒 ${timestamp}</span>
                    <span>🔧 ${data.platform || 'Unknown'}</span>
                </div>
                <button class="download-button" onclick="downloadFile('${data.filename}')">
                    ⬇️ DOWNLOAD FILE
                </button>
            `;
            
            downloadsList.insertBefore(downloadItem, downloadsList.firstChild);
        }
        
        function downloadFile(filename) {
            window.open(`/download_file/${encodeURIComponent(filename)}`, '_blank');
        }
        
        function loadConsoleLogs() {
            fetch('/console_logs')
                .then(response => response.json())
                .then(logs => {
                    const consoleOutput = document.getElementById('consoleOutput');
                    consoleOutput.innerHTML = '';
                    logs.forEach(log => {
                        addConsoleLog(log);
                    });
                });
        }
        
        function updateServerInfo() {
            fetch('/server_info')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('serverInfo').innerHTML = `
                        📁 Downloads: ${data.downloads_dir}<br>
                        ⏰ Time: ${data.current_time}
                    `;
                });
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            updateServerInfo();
            setInterval(updateServerInfo, 10000);
            
            // Test URL examples
            const urlInput = document.getElementById('videoUrl');
            urlInput.addEventListener('focus', function() {
                if (this.value === 'https://www.youtube.com/watch?v=dQw4w9WgXcQ') {
                    this.value = '';
                }
            });
            
            urlInput.addEventListener('blur', function() {
                if (this.value === '') {
                    this.value = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ';
                }
            });
            
            // Load recent downloads
            fetch('/recent_downloads')
                .then(response => response.json())
                .then(downloads => {
                    const downloadsList = document.getElementById('downloadItems');
                    downloads.forEach(download => {
                        const downloadItem = document.createElement('div');
                        downloadItem.className = 'download-item';
                        
                        downloadItem.innerHTML = `
                            <div class="download-filename">📁 ${download.filename}</div>
                            <div class="download-info">
                                <span>📦 ${download.size_mb} MB</span>
                                <span>🕒 ${download.timestamp}</span>
                                <span>🔧 ${download.platform || 'Unknown'}</span>
                            </div>
                            <button class="download-button" onclick="downloadFile('${download.filename}')">
                                ⬇️ DOWNLOAD FILE
                            </button>
                        `;
                        
                        downloadsList.appendChild(downloadItem);
                    });
                });
        });
    </script>
</body>
</html>
'''

@app.route('/download', methods=['POST'])
def start_download():
    """Start a new download"""
    try:
        data = request.json
        url = data.get('url')
        quality = data.get('quality', 'best')
        format_type = data.get('format', 'mp4')
        
        if not url:
            return jsonify({'success': False, 'error': 'No URL provided'})
        
        # Queue the download
        task_id = downloader.queue_download(url, quality, format_type)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Download queued'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/progress/<task_id>')
def get_progress(task_id):
    """Get download progress"""
    try:
        if task_id in download_tasks:
            task_data = download_tasks[task_id]
            if task_data.get('success') is not None:
                # Task completed
                task_data.setdefault('status', 'completed' if task_data.get('success') else 'error')
                return jsonify(task_data)
            else:
                # Task in progress
                return jsonify({
                    'status': 'downloading',
                    'progress': task_data.get('progress', '0%'),
                    'current_line': task_data.get('current_line', 'Processing...')
                })
        else:
            return jsonify({
                'status': 'queued',
                'progress': '0%',
                'current_line': 'Waiting in queue...'
            })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/download_file/<filename>')
def download_file(filename):
    """Download a file"""
    try:
        filepath = os.path.join(downloader.downloads_dir, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/recent_downloads')
def get_recent_downloads():
    """Get recent downloads"""
    try:
        downloads = []
        for task_id, download in active_downloads.items():
            if download.get('status') == 'completed':
                downloads.append({
                    'filename': download['filename'],
                    'size_mb': download['size_mb'],
                    'timestamp': download['timestamp'],
                    'platform': download.get('platform', 'unknown')
                })
        
        # Sort by timestamp (newest first)
        downloads.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify(downloads[:10])  # Return last 10 downloads
    except Exception as e:
        return jsonify([])

@app.route('/server_info')
def server_info():
    """Get server information"""
    return jsonify({
        'server_url': downloader.server_url,
        'local_ip': downloader.local_ip,
        'downloads_dir': downloader.downloads_dir,
        'current_time': datetime.now().strftime("%H:%M:%S"),
        'total_downloads': len(active_downloads)
    })

@app.route('/console_logs')
def get_console_logs():
    """Get console logs"""
    return jsonify(console_logs)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("🔥🔥🔥 REDX VIDEO DOWNLOADER 🔥🔥🔥")
    print("=" * 50)
    print(f"📱 Server running at port: {port}")
    print(f"📁 Downloads folder: {downloader.downloads_dir}")
    print("🛠  Made by: @REDX_64")
    print("=" * 50)
    
    # Run Flask server with dynamic port support for Render
    app.run(host='0.0.0.0', port=port)
