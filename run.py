import threading
import webview
from app2 import app

def run_flask():
    app.run()

flask_thread = threading.Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

webview.create_window("National Team", "https://127.0.0.1:5000", width=1200, height=800)