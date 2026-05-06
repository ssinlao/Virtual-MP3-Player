import os
import vlc
import threading
import queue
import time
from flask import Flask, render_template, request, jsonify

try:
    os.add_dll_directory(r'C:\Program Files\VideoLAN\VLC')
except AttributeError:
    pass 

app = Flask(__name__)

COMMAND_QUEUE = queue.Queue()  # FIFO for deferred interrupt processing
AUDIO_RING_BUFFER = queue.Queue(maxsize=10) 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

playlist = [os.path.join(BASE_DIR, f) for f in os.listdir(BASE_DIR) if f.endswith('.mp3')]
current_track_index = 0

# "Hardware" (VLC)
player = vlc.MediaPlayer()

# I/O interrupt handler -> triggered by 'signal bus' which is the buttons in the UI
def io_interrupt_handler(signal_type, payload=None):
    print(f"\n[IRQ] Interrupt Detected on IO_{signal_type}")
    COMMAND_QUEUE.put({'type': signal_type, 'data': payload})

# main audio loop
def audio_manager_thread():
    global current_track_index
    print(f"[SYSTEM] Booting... Found {len(playlist)} files in root.")

    if playlist:
        media = vlc.Media(playlist[current_track_index].replace('\\', '/'))
        player.set_media(media)
        print(f"[SYSTEM] Loaded: {playlist[current_track_index]}")
    
    buffer_fill_tick = 0
    buffer_consume_tick = 0
    
    while True:
        # command queue -> when button is pressed a command is added to the command queue and the CPU
        # decides whether or not to handle it and then does the command

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
                    
                    # Clear buffer on song switch
                    while not AUDIO_RING_BUFFER.empty():
                        AUDIO_RING_BUFFER.get()
                    buffer_fill_tick = 0
                    buffer_consume_tick = 0
            
            elif cmd['type'] == "PREV":
                if playlist:
                    current_track_index = (current_track_index - 1) % len(playlist)
                    media = vlc.Media(playlist[current_track_index])
                    player.set_media(media)
                    player.play()
                    print(f"[SYSTEM] Loaded: {playlist[current_track_index]}")
                    # Clear buffer on song switch
                    while not AUDIO_RING_BUFFER.empty():
                        AUDIO_RING_BUFFER.get()
                    buffer_fill_tick = 0
                    buffer_consume_tick = 0
            
            elif cmd['type'] == "VOLUME":
                player.audio_set_volume(int(cmd['data']))

            elif cmd['type'] == "SEEK":
                player.set_position(float(cmd['data']))
                while not AUDIO_RING_BUFFER.empty():
                    AUDIO_RING_BUFFER.get()
                buffer_fill_tick = 0
                buffer_consume_tick = 0

        # DMA & Buffer Management -> when audio is output through the listening device (ex. headphones)
        # audio is "produced" then "consumed" by the headphone output
        # buffer is to preload audio so that even if a command occurs, the audio is never forced to stop due to process management
        if player.is_playing():
            buffer_fill_tick += 1
            buffer_consume_tick += 1

            # Add data segments to buffer every 250ms
            if buffer_fill_tick >= 2 and not AUDIO_RING_BUFFER.full():
                timestamp_code = f"{int(time.time() * 1_000_000) % 1_000_000:06d}"
                AUDIO_RING_BUFFER.put(timestamp_code)
                buffer_fill_tick = 0

            # Consume from buffer every 500ms
            if buffer_consume_tick >= 5 and not AUDIO_RING_BUFFER.empty():
                AUDIO_RING_BUFFER.get()
                buffer_consume_tick = 0

        time.sleep(0.1) # 100ms system tick

# Start the 'Microcontroller' Thread
threading.Thread(target=audio_manager_thread, daemon=True).start()

# SIGNAL BUS (Flask Routes) -> logic for the buttons in the virtual mp3 player

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/play', methods=['POST'])
def trigger_play():
    io_interrupt_handler("PLAY")
    return jsonify({"status": "ACK"})

@app.route('/next', methods=['POST'])
def trigger_next():
    io_interrupt_handler("NEXT")
    return jsonify({"status": "ACK"})

@app.route('/prev', methods=['POST'])
def trigger_prev():
    io_interrupt_handler("PREV")
    return jsonify({"status": "ACK"})

@app.route('/volume', methods=['POST'])
def trigger_volume():
    level = request.form.get('level')
    io_interrupt_handler("VOLUME", payload=level)
    return jsonify({"status": "ACK"})

@app.route('/seek', methods=['POST'])
def trigger_seek():
    pos = request.form.get('pos')
    io_interrupt_handler("SEEK", payload=pos)
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

@app.route('/buffer-status')
def get_buffer_status():
    return jsonify({
        "items": list(AUDIO_RING_BUFFER.queue),
        "capacity": 10
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000, use_reloader=False)