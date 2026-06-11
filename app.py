from flask import Flask, Response
import requests
import os

app = Flask(__name__)

# ESP32 IP'sini environment variable'dan al
ESP32_URL = os.getenv('ESP32_URL', 'http://192.168.137.67:80')

@app.route('/')
def index():
    return '''
    <html>
    <head><title>VisionGuard Remote</title></head>
    <body style="background:black; margin:0;">
        <img src="/stream" style="width:100%; height:auto;">
    </body>
    </html>
    '''

@app.route('/stream')
def stream():
    """ESP32'den stream'i relay et"""
    def generate():
        try:
            r = requests.get(f'{ESP32_URL}/stream', stream=True, timeout=30)
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    yield chunk
        except Exception as e:
            print(f"Stream error: {e}")
            yield b''
    
    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={'Connection': 'close'}
    )

@app.route('/health')
def health():
    """Cron job tarafından çağrılacak (sunucuyu açık tutmak için)"""
    return {'status': 'ok'}, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
