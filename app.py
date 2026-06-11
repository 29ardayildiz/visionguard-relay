from flask import Flask, Response, request
import time
import os
import threading

app = Flask(__name__)

latest_frame = None
last_update = 0
SECRET_KEY = os.getenv('SECRET_KEY')
frame_event = threading.Event()  # ← Yeni frame gelince sinyal gönderir

@app.route('/push', methods=['POST'])
def push_frame():
    global latest_frame, last_update
    
    key = request.headers.get('X-Secret-Key')
    if key != SECRET_KEY:
        return 'Unauthorized', 401
    
    latest_frame = request.data
    last_update = time.time()
    frame_event.set()    # ← Yeni frame geldi, stream'e haber ver
    frame_event.clear()  # ← Hemen sıfırla
    return 'OK', 200

@app.route('/stream')
def stream():
    def generate():
        while True:
            frame_event.wait(timeout=1.0)  # ← Frame gelene kadar bekle (max 1s)
            if latest_frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' +
                       latest_frame + b'\r\n')
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    return {'status': 'ok', 'last_frame_age': time.time() - last_update}, 200

@app.route('/')
def index():
    return '''
    <html>
    <head><title>VisionGuard Remote</title></head>
    <body style="background:black; margin:0; display:flex;
                 justify-content:center; align-items:center;
                 min-height:100vh;">
        <img src="/stream" style="max-width:100%; height:auto;">
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
