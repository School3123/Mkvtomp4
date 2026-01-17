import os
import threading
import time
import subprocess
import libtorrent as lt
import re
import psutil  # 追加: システム監視用
import platform # 追加: CPU情報用

# GPUライブラリの読み込みトライ (GPUがない環境でのエラー防止)
try:
    import GPUtil
    HAS_GPU_LIB = True
except ImportError:
    HAS_GPU_LIB = False

from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# --- (既存のディレクトリ設定や関数はそのまま) ---
DOWNLOAD_DIR = 'downloads'
CONVERT_DIR = 'converted'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(CONVERT_DIR, exist_ok=True)

tasks = {
    "torrent": {"status": "idle", "progress": 0, "name": ""},
    "convert": {"status": "idle", "output": "", "progress": 0, "eta": "-"}
}

# --- (既存の torrent_download_thread, get_video_duration, time_str_to_sec, ffmpeg_convert_thread は変更なし) ---
# ※省略します。以前のコードをそのまま維持してください。
# ただし、ffmpeg_convert_thread などは以前のコードが必要です。

# --- 追加: システム情報を取得するAPI ---
@app.route('/system_info')
def system_info():
    # 1. CPU情報
    cpu_percent = psutil.cpu_percent(interval=None) # 非ブロッキングで取得
    cpu_freq = psutil.cpu_freq()
    current_freq = round(cpu_freq.current, 0) if cpu_freq else 0
    
    # 2. メモリ情報
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_used_gb = round(mem.used / (1024**3), 1)
    mem_total_gb = round(mem.total / (1024**3), 1)

    # 3. GPU情報 (NVIDIAのみ)
    gpu_list = []
    if HAS_GPU_LIB:
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_list.append({
                    "name": gpu.name,
                    "load": round(gpu.load * 100, 1),
                    "memory_used": round(gpu.memoryUsed, 0),
                    "memory_total": round(gpu.memoryTotal, 0),
                    "temp": gpu.temperature
                })
        except Exception:
            pass # エラー時は空リスト

    return jsonify({
        "cpu": {
            "name": platform.processor(),
            "percent": cpu_percent,
            "freq": current_freq
        },
        "memory": {
            "percent": mem_percent,
            "used": mem_used_gb,
            "total": mem_total_gb
        },
        "gpus": gpu_list
    })

# --- (既存のルート定義) ---
# get_recursive_files関数、indexルート、add_magnet, start_convert, status, download_file などは
# 以前のコードをそのまま使ってください。

def get_recursive_files(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if not file.startswith('.'):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, directory)
                file_list.append(rel_path)
    return sorted(file_list)

@app.route('/')
def index():
    files = get_recursive_files(DOWNLOAD_DIR)
    converted_files = [f for f in os.listdir(CONVERT_DIR) if os.path.isfile(os.path.join(CONVERT_DIR, f))]
    return render_template('index.html', files=files, converted_files=converted_files)

@app.route('/add_magnet', methods=['POST'])
def add_magnet():
    magnet = request.form.get('magnet_link')
    if magnet:
        thread = threading.Thread(target=torrent_download_thread, args=(magnet,))
        thread.start()
        return jsonify({"message": "Download started"}), 200
    return jsonify({"error": "No link provided"}), 400

@app.route('/start_convert', methods=['POST'])
def start_convert():
    filename = request.form.get('filename')
    preset = request.form.get('preset')
    crf = request.form.get('crf', 23)
    encoder = request.form.get('encoder', 'libx264')
    if filename and preset:
        # ここでは ffmpeg_convert_thread が定義されている前提
        thread = threading.Thread(target=ffmpeg_convert_thread, args=(filename, preset, crf, encoder))
        thread.start()
        return jsonify({"message": "Conversion started"}), 200
    return jsonify({"error": "Invalid parameters"}), 400

@app.route('/status')
def status():
    return jsonify(tasks)

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(CONVERT_DIR, filename, as_attachment=True)

# --- 以下略 (torrent_download_thread, ffmpeg_convert_thread の定義を忘れずに) ---
# ※省略されていますが、以前のステップで作成した関数を必ずここに含めてください。

def torrent_download_thread(magnet_link):
    # (省略: 以前のコードを使用)
    pass 

def ffmpeg_convert_thread(rel_path, preset, crf, encoder):
    # (省略: 以前のコードを使用)
    pass

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
