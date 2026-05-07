import os
from flask import Flask

app = Flask(__name__, static_folder='static')
print(f"Static folder path: {app.static_folder}")
print(f"Static folder exists: {os.path.exists(app.static_folder)}")
if os.path.exists(app.static_folder):
    print(f"Contents: {os.listdir(app.static_folder)}")
    index_path = os.path.join(app.static_folder, 'index.html')
    print(f"Index.html path: {index_path}")
    print(f"Index.html exists: {os.path.exists(index_path)}")
