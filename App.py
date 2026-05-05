import os
import vlc
import threading
import queue
import time
from flask import Flask, render_template, request, jsonify

# ==========================================
# WINDOWS OS FIX: Locate the VLC Device Driver
# ==========================================
try:
    os.add_dll_directory(r'C:\Program Files\VideoLAN\VLC')
except AttributeError:
    pass 

app = Flask(__name__)

# --- HARDWARE MEMORY MAP ---
COMMAND_QUEUE = queue.Queue()  # FIFO for deferred interrupt processing
AUDIO_RING_BUFFER = queue.Queue(maxsize=10) 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Scan for MP3s in the root folder
playlist = [os.path.join(BASE_DIR, f) for f in os.listdir(BASE_DIR) if f.endswith('.mp3')]
current_track_index = 0

# Peripheral Hardware (VLC)
player = vlc.MediaPlayer()
# --- 1. INTERRUPT SERVICE ROUTINE (ISR) ---
def gpio_interrupt_handler(signal_type, payload=None):
    """
    Simulates a Hardware Interrupt handler.
    Triggered by the Flask 'Signal Bus' (UI Buttons).
    """
    print(f"\n[IRQ] Interrupt Detected on GPIO_{signal_type}")
    COMMAND_QUEUE.put({'type': signal_type, 'data': payload})

# --- 2. THE MAIN SYSTEM LOOP (CPU) ---
def audio_manager_thread():
    global current_track_index
    print(f"[SYSTEM] Booting... Found {len(playlist)} files in root.")

    if playlist:
        media = vlc.Media(playlist[current_track_index].replace('\\', '/'))
        player.set_media(media)
        print(f"[SYSTEM] Loaded: {playlist[current_track_index]}")
    
    while True:
        # A. Command Decoder: Only process if there's an interrupt in the queue
        if not COMMAND_QUEUE.empty():
            cmd = COMMAND_QUEUE.get()
            print(f"[CPU] Execution Unit: Handling {cmd['type']}")
            
            if cmd['type'] == "PLAY":
                if player.is_playing():
                    player.pause()
                else:
                    player.play()
            
            elif cmd['type'] == "NEXT":
                if playlist:
                    current_track_index = (current_track_index + 1) % len(playlist)
                    media = vlc.Media(playlist[current_track_index])
                    player.set_media(media)
                    player.play()
                    print(f"[SYSTEM] Loaded: {playlist[current_track_index]}")
            
            elif cmd['type'] == "PREV":
                if playlist:
                    current_track_index = (current_track_index - 1) % len(playlist)
                    media = vlc.Media(playlist[current_track_index])
                    player.set_media(media)
                    player.play()
                    print(f"[SYSTEM] Loaded: {playlist[current_track_index]}")
            
            elif cmd['type'] == "VOLUME":
                player.audio_set_volume(int(cmd['data']))

            elif cmd['type'] == "SEEK":
                player.set_position(float(cmd['data']))

        # B. DMA & Buffer Management (Only runs if music is active)
        if player.is_playing():
            if not AUDIO_RING_BUFFER.full():
                AUDIO_RING_BUFFER.put(f"DATA_SEGMENT_{time.time()}")
                # print(f"[DMA] Buffering... {AUDIO_RING_BUFFER.qsize()}/10") # Quiet mode

            if not AUDIO_RING_BUFFER.empty():
                AUDIO_RING_BUFFER.get()

        time.sleep(0.1) # 100ms system tick

# Start the 'Microcontroller' Thread
threading.Thread(target=audio_manager_thread, daemon=True).start()

# --- 3. SIGNAL BUS (Flask Routes) ---
# These must match the 'fetch' routes in your index.html

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/play', methods=['POST'])
def trigger_play():
    gpio_interrupt_handler("PLAY")
    return jsonify({"status": "ACK"})

@app.route('/next', methods=['POST'])
def trigger_next():
    gpio_interrupt_handler("NEXT")
    return jsonify({"status": "ACK"})

@app.route('/prev', methods=['POST'])
def trigger_prev():
    gpio_interrupt_handler("PREV")
    return jsonify({"status": "ACK"})

@app.route('/volume', methods=['POST'])
def trigger_volume():
    level = request.form.get('level')
    gpio_interrupt_handler("VOLUME", payload=level)
    return jsonify({"status": "ACK"})

@app.route('/seek', methods=['POST'])
def trigger_seek():
    pos = request.form.get('pos')
    gpio_interrupt_handler("SEEK", payload=pos)
    return jsonify({"status": "ACK"})

@app.route('/status')
def get_status():
    # Polling route for the UI LCD
    song_name = os.path.basename(playlist[current_track_index]) if playlist else "No Media"
    return jsonify({
        "pos": player.get_position(),
        "is_playing": player.is_playing(),
        "current_song": song_name
    })

@app.route('/progress')
def get_progress():
    return jsonify({
        "current": player.get_time(),
        "total": player.get_length()
    })

if __name__ == '__main__':
    # use_reloader=False prevents the thread from starting twice
    app.run(debug=True, port=5000, use_reloader=False)