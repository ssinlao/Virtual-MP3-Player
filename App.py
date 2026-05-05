import os
import vlc
import threading
import queue
import time
from flask import Flask, render_template, jsonify

# ==========================================
# WINDOWS OS FIX: Locate the VLC Device Driver
# ==========================================
try:
    os.add_dll_directory(r'C:\Program Files\VideoLAN\VLC')
except AttributeError:
    pass 

app = Flask(__name__)

# OS CONCEPT 1: Inter-Process Communication (IPC) via Queues
command_queue = queue.Queue()

def get_playlist():
    playlist_files = [f.replace('.mp3', '') for f in os.listdir('.') if f.endswith('.mp3')]
    if len(playlist_files) == 0:
        return ["No Music Found"]
    return playlist_files

playlist = get_playlist()
current_track_index = 0
player = vlc.MediaPlayer()

# ==========================================
# OS CONCEPT 2: Process Management (Consumer)
# ==========================================
def audio_manager_thread():
    global current_track_index
    print("\n[OS Scheduler] 🧵 Audio Subsystem Thread Initialized and Waiting...\n")
    
    while True:
        # The thread sleeps here until the OS passes a message into the queue
        command = command_queue.get()
        
        if command == "PLAY":
            player.stop()
            if playlist[0] != "No Music Found":
                song_file = playlist[current_track_index] + ".mp3"
                media = vlc.Media(song_file)
                player.set_media(media)
                player.play()
                print(f"[Audio Thread] 🎵 Hardware I/O Active: Playing {song_file}")
                
        elif command == "STOP":
            player.stop()
            print("[Audio Thread] ⏹️ Interrupt Handled: Hardware I/O Halted.")
            
        elif command == "NEXT":
            current_track_index = (current_track_index + 1) % len(playlist)
            command_queue.put("PLAY")
            
        elif command == "PREV":
            current_track_index = (current_track_index - 1) % len(playlist)
            command_queue.put("PLAY")
            
        elif command.startswith("VOL:"):
            level = int(command.split(":")[1])
            player.audio_set_volume(level)
            print(f"[Audio Thread] 🔊 Hardware Driver updated volume to {level}%")

        command_queue.task_done()

# Start the OS Audio Subsystem Thread BEFORE the web server starts
audio_thread = threading.Thread(target=audio_manager_thread, daemon=True)
audio_thread.start()

@app.route('/')
def home():
    return render_template('index.html')

# ==========================================
# OS CONCEPT 3: Flask Producer Threads
# ==========================================
@app.route('/api/play')
def play_music():
    command_queue.put("PLAY")
    return jsonify({"status": "success", "message": "Play signal sent to OS thread."})

@app.route('/api/stop')
def stop_music():
    command_queue.put("STOP")
    return jsonify({"status": "success", "message": "Stop signal sent to OS thread."})

@app.route('/api/next')
def next_track():
    command_queue.put("NEXT")
    return jsonify({"status": "success", "message": "Next signal sent to OS thread."})

@app.route('/api/prev')
def prev_track():
    command_queue.put("PREV")
    return jsonify({"status": "success", "message": "Prev signal sent to OS thread."})

@app.route('/api/volume/<int:level>')
def set_volume(level):
    command_queue.put(f"VOL:{level}")
    return jsonify({"status": "success", "message": "Volume signal sent."})

@app.route('/api/current_song')
def get_current_song():
    return jsonify({"song": playlist[current_track_index]})

@app.route('/api/progress')
def get_progress():
    return jsonify({"current": player.get_time(), "total": player.get_length()})

@app.route('/api/seek/<int:time_ms>')
def seek_audio(time_ms):
    player.set_time(time_ms)
    return jsonify({"status": "success", "message": "Scrubbed to new time."})

if __name__ == '__main__':
    # use_reloader=False is CRITICAL for multithreading on Windows so it doesn't duplicate the audio thread
    app.run(debug=True, port=5000, use_reloader=False)