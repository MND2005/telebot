import subprocess
import time

while True:
    print("Starting bot...")
    process = subprocess.Popen(["python", "app.py"])
    process.wait()
    print("Bot crashed! Restarting in 5 seconds...")
    time.sleep(5)
