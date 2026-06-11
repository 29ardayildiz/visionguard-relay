from flask import Flask, Response, request
import time

app = Flask(__name__)

# Son gelen frame'i bellekte tut
latest_frame = None
last_update = 0

@app.route('/push', methods=['POST'])
def push_frame():
    """ESP32 buraya frame gönderir"""
    global latest_frame, last_update
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
    return {'status': 'ok'}, 200

@app.route('/')
def index():
    return '''
    <html>
    <body style="background:black; margin:0;">
        <img src="/stream" style="width:100%;">
    </body>
    </html>
    '''
