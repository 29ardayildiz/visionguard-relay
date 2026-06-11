from flask import Flask, Response, request
import time
import os

app = Flask(__name__)

# Frame storage
latest_frame = None
last_update = 0

# Secret key from environment variable
SECRET_KEY = os.getenv('SECRET_KEY')

@app.route('/push', methods=['POST'])
def push_frame():
    """ESP32 buraya frame gönderir"""
    global latest_frame, last_update
    
    # Secret key kontrolü
    key = request.headers.get('X-Secret-Key')
    if key != SECRET_KEY:
        return 'Unauthorized', 401
    
    latest_frame = request.data
    last_update = time.time()
    return 'OK', 200

@app.route('/stream')
def stream():
    """Tarayıcı buradan izler"""
    def generate():
        while True:
            if latest_frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       latest_frame + b'\r\n')
            time.sleep(0.1)
    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    """Cron job için - sunucuyu açık tutar"""
    return {'status': 'ok', 'last_frame_age': time.time() - last_update}, 200

@app.route('/')
def index():
    """Ana sayfa - stream gösterir"""
    return '''
    <html>
    <head>
        <title>VisionGuard Remote</title>
    </head>
    <body style="background:black; margin:0; display:flex; 
                 justify-content:center; align-items:center; 
                 min-height:100vh;">
        <img src="/stream" style="max-width:100%; height:auto;">
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
