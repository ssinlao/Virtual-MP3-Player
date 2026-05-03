import os

# Your VLC Windows Fix (Keep this!)
try:
    os.add_dll_directory(r'C:\Program Files\VideoLAN\VLC')
except AttributeError:
    pass 

import vlc
from flask import Flask, render_template, jsonify

app = Flask(__name__)

#DYNAMIC FOLDER SCANNING
playlist = []

for file in os.listdir('.'):
    if file.endswith('.mp3'):
        clean_name = file.replace('.mp3', '')
        playlist.append(clean_name)

# Fallback just in case the folder is empty so the app doesn't crash
if len(playlist) == 0:
    playlist = ["No Music Found"]

current_track_index = 0

# Initialize the VLC player object
player = vlc.MediaPlayer()

def play_current_song():
    player.stop() 
    
    # Don't try to play audio if the folder was empty!
    if playlist[0] == "No Music Found":
        return

    song_file = playlist[current_track_index] + ".mp3"
    
    media = vlc.Media(song_file)
    player.set_media(media)
    player.play()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/play')
def play_music():
    print(f"\n🔊 Hardware Command: Playing {playlist[current_track_index]}\n")
    play_current_song() # Call our new helper function
    return jsonify({"status": "success", "message": "Playing Music!"})

@app.route('/api/stop')
def stop_music():
    print("\n⏹️ Hardware Command: Stopping music.\n")
    player.stop() # Tell VLC to stop the audio
    return jsonify({"status": "success", "message": "Music Stopped."})

@app.route('/api/volume/<int:level>')
def set_volume(level):
    # VLC accepts volume levels from 0 to 100
    player.audio_set_volume(level)
    
    print(f"\n🔊 Hardware Command: Volume changed to {level}%\n")
    return jsonify({"status": "success", "message": f"Volume set to {level}%"})

@app.route('/api/current_song')
def get_current_song():
    song_name = playlist[current_track_index]
    return jsonify({"song": song_name})

@app.route('/api/next')
def next_track():
    global current_track_index
    current_track_index = (current_track_index + 1) % len(playlist)
    
    print(f"\n⏭️ Hardware Command: Skipping to {playlist[current_track_index]}!\n")
    play_current_song() # Automatically play the new track
    return jsonify({"status": "success", "message": "Skipped to Next Track."})

@app.route('/api/prev')
def prev_track():
    global current_track_index
    current_track_index = (current_track_index - 1) % len(playlist)
    
    print(f"\n⏮️ Hardware Command: Going back to {playlist[current_track_index]}!\n")
    play_current_song() # Automatically play the new track
    return jsonify({"status": "success", "message": "Returned to Previous Track."})

@app.route('/api/progress')
def get_progress():
    # VLC calculates time in milliseconds (1 second = 1000 ms)
    # If no song is playing, these will return -1
    current_time = player.get_time()
    total_length = player.get_length()
    
    return jsonify({
        "current": current_time,
        "total": total_length
    })

@app.route('/api/seek/<int:time_ms>')
def seek_audio(time_ms):
    # This tells VLC to jump to a specific millisecond
    player.set_time(time_ms)
    return jsonify({"status": "success", "message": "Scrubbed to new time."})
    
if __name__ == '__main__':
    app.run(debug=True, port=5000)
#when implementing code into the pi change the code above this into the code below this
#if __name__ == '__main__':
#    app.run(host='0.0.0.0', port=5000, debug=True)