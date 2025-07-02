# -*- coding: utf-8 -*-
"""
Autoexec Plugin: автоматически выполняет скрипт autoexec_script.py при запуске MakeHuman.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from core import G
from typing import TYPE_CHECKING, cast
import os
import tempfile
import zipfile
if TYPE_CHECKING:
    from .autoexec_plugin import AppHTTPServer

def plugin_log(msg):
    log_path = os.path.join(os.path.dirname(__file__), "plugin_debug.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def export_model(path):
    from shared import wavefront
    human = G.app.selectedHuman
    if not human:
        plugin_log("No selected human to export")
        return False, "No selected human"
    try:
        wavefront.writeObjFile(path, human.mesh)
        plugin_log(f"Model exported to {path}")
        return True, f"Model exported to {path}"
    except Exception as e:
        plugin_log(f"Export failed: {e}")
        return False, str(e)

def make_zip(obj_path, mtl_path, zip_path):
    with zipfile.ZipFile(zip_path, "w") as zipf:
        zipf.write(obj_path, arcname="model.obj")
        if os.path.exists(mtl_path):
            zipf.write(mtl_path, arcname="model.mtl")

class RequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            params = json.loads(post_data.decode('utf-8'))

            def task():
                apply_params(params)
                export_path = "model.obj"
                success, msg = export_model(export_path)
                plugin_log(f"Export: {msg}")
            event = threading.Event()
            def wrapper():
                task()
                event.set()
            cast(AppHTTPServer, self.server).app.callAsync(wrapper)
            event.wait()

            obj_path = "model.obj"
            mtl_path = "model.mtl"
            zip_path = "model.zip"
            make_zip(obj_path, mtl_path, zip_path)

            if os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    zip_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Disposition", 'attachment; filename="model.zip"')
                self.send_header("Content-Length", str(len(zip_data)))
                self.end_headers()
                self.wfile.write(zip_data)
                plugin_log("[autoexec_plugin] Архив model.zip отправлен в ответе")
                os.remove(zip_path)
            else:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Model zip not found")

        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))


class AppHTTPServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, app):
        super().__init__(server_address, RequestHandlerClass)
        self.app = app

def run_server(app):
    server = AppHTTPServer(('127.0.0.1', 5005), RequestHandler, app)
    print("[autoexec_plugin] HTTP сервер запущен на 127.0.0.1:5005")
    server.serve_forever()

def load(app):
    t = threading.Thread(target=run_server, args=(app,), daemon=True)
    t.start()

def apply_params(params):
    human = G.app.selectedHuman
    for name, value in params.items():
        modifier = human.getModifier(name)
        if modifier:
            modifier.setValue(value)
    human.applyAllTargets()
    plugin_log(f"Parameters applied: {params}") 