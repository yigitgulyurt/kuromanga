import os
import json
from datetime import datetime
from flask import request, session, current_app

def ensure_storage(log_dir, user_log_dir):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    if not os.path.exists(user_log_dir):
        os.makedirs(user_log_dir)

def log_activity(event_type="TRAFFIC", username=None):
    log_dir = current_app.config.get("ACTIVITY_LOGS_PATH")
    user_log_dir = current_app.config.get("USER_LOGS_PATH")
    
    if not log_dir or not user_log_dir:
        return

    ensure_storage(log_dir, user_log_dir)
    
    master_log = os.path.join(log_dir, "activity.log")
    
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    path = request.path
    method = request.method
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Try to get username from session if not provided
    if not username and 'user_id' in session:
        try:
            from app.models.user import User
            user = User.query.get(session['user_id'])
            if user:
                username = user.username
        except Exception:
            pass

    log_entry = {
        "timestamp": timestamp,
        "event": event_type,
        "ip": ip,
        "user_agent": user_agent,
        "path": path,
        "method": method,
        "username": username or "Anonymous"
    }
    
    log_json = json.dumps(log_entry, ensure_ascii=False) + "\n"
    
    try:
        # 1. Master Log (Her şeyi tek bir yerde tutmaya devam et)
        with open(master_log, "a", encoding="utf-8") as f:
            f.write(log_json)
            
        # 2. Ayrıştırılmış Loglar
        if username:
            # Kullanıcıya özel dosya: storage/logs/users/kullanici_adi.log
            user_file = os.path.join(user_log_dir, f"{username}.log")
            with open(user_file, "a", encoding="utf-8") as f:
                f.write(log_json)
        else:
            # Anonim trafik dosyası: storage/logs/anonymous.log
            anon_file = os.path.join(log_dir, "anonymous.log")
            with open(anon_file, "a", encoding="utf-8") as f:
                f.write(log_json)
                
    except Exception as e:
        print(f"Logging error: {e}")
