from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return "<h1>Télémétrie Drone - Station de contrôle</h1><p>En attente de données...</p>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)