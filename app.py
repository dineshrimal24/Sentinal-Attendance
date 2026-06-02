import os
import io
import base64
from datetime import datetime
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, flash, send_from_directory, send_file
import cv2
import numpy as np
from face_handler import FaceHandler
from attendance_manager import AttendanceManager

app = Flask(__name__)
app.secret_key = "SentinelBiometricAttendanceSecretKey"

# Initialize our custom handler and manager
# They will handle directories and model downloading automatically
face_handler = FaceHandler()
attendance_manager = AttendanceManager()

@app.route('/images/<path:filename>')
def serve_user_image(filename):
    """Serves registered face images for display in cards."""
    return send_from_directory(face_handler.image_dir, filename)

@app.route('/')
def dashboard():
    """Renders the main analytics dashboard."""
    stats = attendance_manager.get_daily_stats(face_handler.users)
    recent_logs = attendance_manager.get_recent_logs(10)
    trend_data = attendance_manager.get_last_7_days_stats()
    
    return render_template(
        'dashboard.html', 
        active_page='dashboard', 
        stats=stats, 
        recent_logs=recent_logs, 
        trend_data=trend_data
    )

@app.route('/scanner')
def scanner():
    """Renders the camera scanning page."""
    return render_template('scanner.html', active_page='scanner')

def gen_frames():
    """Generator for streaming processed real-time camera frames."""
    # Attempt CAP_DSHOW on Windows for fast boot, fall back to default
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not camera.isOpened():
        camera = cv2.VideoCapture(0)
        
    if not camera.isOpened():
        print("Error: Could not open camera device.")
        # Return a warning graphic frame
        err_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(err_frame, "Camera Service Offline", (140, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        _, buffer = cv2.imencode('.jpg', err_frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        return

    # Set frame parameters
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    try:
        while True:
            success, frame = camera.read()
            if not success:
                break
                
            # Flip horizontally for a mirrored preview feel
            frame = cv2.flip(frame, 1)
            
            # Detect and match faces
            results = face_handler.detect_and_recognize(frame)
            
            # Draw HUD elements on frame
            for res in results:
                box = res["box"]
                name = res["name"]
                user_id = res["user_id"]
                score = res["score"]
                x, y, w, h = box
                
                # Determine colors (BGR) and labels
                if user_id == "Unknown":
                    # Glowing neon rose/red for unrecognized faces
                    color = (80, 60, 244) 
                    label = "UNKNOWN"
                else:
                    # Glowing neon cyan for recognized faces
                    color = (212, 182, 6) 
                    label = f"{name} ({score:.2f})"
                    
                    # Log attendance
                    user_info = face_handler.users.get(user_id, {})
                    dept = user_info.get("department", "Unknown")
                    attendance_manager.log_attendance(user_id, name, dept)
                
                # Outer rectangle box
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 1)
                
                # Cyberpunk style thick corner tags
                line_len = min(w, h) // 4
                thick = 3
                
                cv2.line(frame, (x, y), (x + line_len, y), color, thick)
                cv2.line(frame, (x, y), (x, y + line_len), color, thick)
                
                cv2.line(frame, (x + w, y), (x + w - line_len, y), color, thick)
                cv2.line(frame, (x + w, y), (x + w, y + line_len), color, thick)
                
                cv2.line(frame, (x, y + h), (x + line_len, y + h), color, thick)
                cv2.line(frame, (x, y + h), (x, y + h - line_len), color, thick)
                
                cv2.line(frame, (x + w, y + h), (x + w - line_len, y + h), color, thick)
                cv2.line(frame, (x + w, y + h), (x + w, y + h - line_len), color, thick)
                
                # Label Banner
                cv2.rectangle(frame, (x, y - 22), (x + w, y), color, cv2.FILLED)
                cv2.putText(frame, label, (x + 5, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
                
            # Compress and encode frame
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                continue
                
            frame_bytes = jpeg.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    finally:
        # Guarantee camera release when generator is closed (e.g. client disconnects)
        camera.release()
        print("Camera capture stream closed and device released.")

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/users', methods=['GET', 'POST'])
def users():
    """Serves the user directory and handles new enrollment form submissions."""
    if request.method == 'POST':
        user_id = request.form.get('user_id', '').strip()
        name = request.form.get('name', '').strip()
        department = request.form.get('department', '').strip()
        email = request.form.get('email', '').strip()
        source = request.form.get('capture_source', 'webcam')
        
        # Verify required inputs
        if not user_id or not name or not department:
            flash("User ID, Name, and Department are required.", "error")
            return redirect(url_for('users'))
            
        frame = None
        if source == 'webcam':
            # Extract base64 canvas snap
            img_data = request.form.get('image_data', '')
            if img_data:
                try:
                    header, encoded = img_data.split(",", 1)
                    data = base64.b64decode(encoded)
                    nparr = np.frombuffer(data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                except Exception as e:
                    flash(f"Failed to decode captured photo: {e}", "error")
                    return redirect(url_for('users'))
        else:
            # File upload
            file = request.files.get('file')
            if file and file.filename != '':
                try:
                    nparr = np.frombuffer(file.read(), np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                except Exception as e:
                    flash(f"Failed to read uploaded image: {e}", "error")
                    return redirect(url_for('users'))
                    
        if frame is None:
            flash("No image provided. Please capture a photo or upload a file.", "warning")
            return redirect(url_for('users'))
            
        # Register user with FaceHandler
        success, message = face_handler.register_user(user_id, name, department, email, frame)
        if success:
            flash(message, "success")
        else:
            flash(message, "error")
            
        return redirect(url_for('users'))
        
    return render_template('users.html', active_page='users', users=face_handler.users)

@app.route('/reports')
def reports():
    """Serves the logs view and applies search/date filters."""
    name = request.args.get('name', '').strip()
    department = request.args.get('department', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    
    logs = attendance_manager.get_filtered_logs(
        name=name if name else None,
        department=department if department else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None
    )
    
    filters = {
        "name": name,
        "department": department,
        "date_from": date_from,
        "date_to": date_to
    }
    
    return render_template('reports.html', active_page='reports', logs=logs, filters=filters)

@app.route('/api/delete_user/<user_id>', methods=['POST'])
def delete_user(user_id):
    """API endpoint to delete a user registration."""
    success, message = face_handler.delete_user(user_id)
    return jsonify({"success": success, "message": message})

@app.route('/api/recent_scans')
def recent_scans():
    """API endpoint returning the 5 most recent scans for client UI polling."""
    logs = attendance_manager.get_recent_logs(5)
    return jsonify({"logs": logs})

@app.route('/api/export_logs')
def export_logs():
    """API endpoint exporting logs filtered by arguments into CSV or Excel."""
    name = request.args.get('name', '').strip()
    department = request.args.get('department', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    fmt = request.args.get('format', 'csv').strip()
    
    logs = attendance_manager.get_filtered_logs(
        name=name if name else None,
        department=department if department else None,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None
    )
    
    import pandas as pd
    df = pd.DataFrame(logs)
    if df.empty:
        df = pd.DataFrame(columns=['User_ID', 'Name', 'Department', 'Date', 'Time'])
        
    filename_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if fmt == 'excel':
        # Generate Excel buffer in memory
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendance Records')
        out.seek(0)
        return send_file(
            out,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"Attendance_Report_{filename_stamp}.xlsx"
        )
    else:
        # Generate CSV buffer in memory
        out = io.StringIO()
        df.to_csv(out, index=False)
        mem = io.BytesIO()
        mem.write(out.getvalue().encode('utf-8'))
        mem.seek(0)
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"Attendance_Report_{filename_stamp}.csv"
        )

# Automatically register global context variables in all Jinja templates
@app.context_processor
def inject_now():
    return {'year': datetime.now().year}

if __name__ == "__main__":
    print("Launching Sentinel Attendance Server...")
    app.run(host="127.0.0.1", port=5000, debug=True)
