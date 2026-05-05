#!/bin/bash
echo "Starting MP3 Player Setup..."

#Update the system
sudo apt update

#Install the VLC system player
sudo apt install -y vlc

#Install Python libraries from your requirements file
pip install -r requirements.txt

echo "Setup complete! Run 'python app.py' to start the server."