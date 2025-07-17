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
import zipfile
import importlib

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

def apply_clothes(clothes_list):
    """
    Надевает одежду по списку путей к .mhclo файлам.
    """
    try:
        mhapi = getattr(G.app, 'mhapi', None)
        if mhapi is None:
            try:
                mhapi_mod = importlib.import_module('makehuman.plugins.1_mhapi')
                mhapi_mod.load(G.app)
                mhapi = G.app.mhapi
            except Exception as e:
                plugin_log(f"Не удалось инициализировать mhapi: {e}")
                return False
        mhapi.assets.unequipAllClothes()
        for clo in clothes_list:
            plugin_log(f"Пробую надеть: {clo}")
            try:
                mhapi.assets.equipClothes(clo)
                plugin_log(f"Успешно вызван equipClothes для: {clo}")
            except Exception as e:
                plugin_log(f"Ошибка при попытке надеть {clo}: {e}")
        plugin_log(f"Одежда надета: {clothes_list}")
        return True
    except Exception as e:
        plugin_log(f"Ошибка при надевании одежды: {e}")
        return False

def apply_params(params):
    human = G.app.selectedHuman
    clothes = params.pop('clothes', None)
    for name, value in params.items():
        modifier = human.getModifier(name)
        if modifier:
            modifier.setValue(value)
    human.applyAllTargets()
    if clothes:
        if isinstance(clothes, str):
            clothes = [clothes]
        apply_clothes(clothes)
    plugin_log(f"Parameters applied: {params}, clothes: {clothes}")

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
                plugin_log("[autoexec_plugin] Архив model.zip отправлен в ответе (json)")
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
    server = AppHTTPServer(('0.0.0.0', 5005), RequestHandler, app)
    print("[autoexec_plugin] HTTP сервер запущен на 127.0.0.1:5005")
    server.serve_forever()

def load(app):
    t = threading.Thread(target=run_server, args=(app,), daemon=True)
    t.start() 