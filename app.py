import os
import threading
import time
import subprocess
import libtorrent as lt
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# ディレクトリ設定
DOWNLOAD_DIR = 'downloads'
CONVERT_DIR = 'converted'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(CONVERT_DIR, exist_ok=True)

# グローバルステータス管理 (簡易的)
tasks = {
    "torrent": {"status": "idle", "progress": 0, "name": ""},
    "convert": {"status": "idle", "output": ""}
}

def torrent_download_thread(magnet_link):
    """バックグラウンドでTorrentをダウンロードする"""
    tasks["torrent"]["status"] = "starting"
    tasks["torrent"]["progress"] = 0
    
    ses = lt.session()
    ses.listen_on(6881, 6891)
    
    params = lt.parse_magnet_uri(magnet_link)
    params.save_path = DOWNLOAD_DIR
    
    handle = ses.add_torrent(params)
    tasks["torrent"]["name"] = handle.name()
    
    print(f"Downloading Metadata for {magnet_link}...")
    while not handle.has_metadata():
        time.sleep(1)
    
    tasks["torrent"]["name"] = handle.name()
    print(f"Metadata received. Name: {handle.name()}")
    
    while handle.status().state != lt.torrent_status.seeding:
        s = handle.status()
        progress = s.progress * 100
        tasks["torrent"]["status"] = "downloading"
        tasks["torrent"]["progress"] = round(progress, 2)
        tasks["torrent"]["name"] = s.name
        
        # 状態確認用ログ
        # print(f'{s.name}: {progress:.2f}% complete (down: {s.download_rate / 1000:.1f} kB/s)')
        time.sleep(1)
        
    tasks["torrent"]["status"] = "complete"
    tasks["torrent"]["progress"] = 100
    print("Download complete")


def ffmpeg_convert_thread(filename, preset, crf):
    """バックグラウンドでFFmpeg変換を実行する"""
    tasks["convert"]["status"] = "converting"
    
    input_path = os.path.join(DOWNLOAD_DIR, filename)
    output_filename = os.path.splitext(filename)[0] + ".mp4"
    output_path = os.path.join(CONVERT_DIR, output_filename)
    
    # FFmpegコマンド構築
    # H.264 (libx264), 音声はAAC, 指定されたプリセットとCRFを使用
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-c:v', 'libx264',
        '-preset', preset,
        '-crf', str(crf),
        '-c:a', 'aac',
        '-b:a', '128k',
        output_path
    ]
    
    print(f"Running FFmpeg: {' '.join(cmd)}")
    
    try:
        # プロセス実行
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            tasks["convert"]["status"] = "complete"
            tasks["convert"]["output"] = output_filename
        else:
            tasks["convert"]["status"] = "error"
            print("FFmpeg Error:", stderr.decode('utf-8'))
            
    except Exception as e:
        tasks["convert"]["status"] = "error"
        print(f"Conversion Exception: {e}")

@app.route('/')
def index():
    # ダウンロード済みフォルダ内のファイルリストを取得
    files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))]
    # 変換済みフォルダ内のファイルリスト
    converted_files = [f for f in os.listdir(CONVERT_DIR) if os.path.isfile(os.path.join(CONVERT_DIR, f))]
    return render_template('index.html', files=files, converted_files=converted_files)

@app.route('/add_magnet', methods=['POST'])
def add_magnet():
    magnet = request.form.get('magnet_link')
    if magnet:
        # スレッドでダウンロード開始
        thread = threading.Thread(target=torrent_download_thread, args=(magnet,))
        thread.start()
        return jsonify({"message": "Download started"}), 200
    return jsonify({"error": "No link provided"}), 400

@app.route('/start_convert', methods=['POST'])
def start_convert():
    filename = request.form.get('filename')
    preset = request.form.get('preset') # veryslow, medium, ultrafast etc.
    crf = request.form.get('crf', 23)   # 画質設定 (デフォルト23)
    
    if filename and preset:
        # スレッドで変換開始
        thread = threading.Thread(target=ffmpeg_convert_thread, args=(filename, preset, crf))
        thread.start()
        return jsonify({"message": "Conversion started"}), 200
    return jsonify({"error": "Invalid parameters"}), 400

@app.route('/status')
def status():
    return jsonify(tasks)

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(CONVERT_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
