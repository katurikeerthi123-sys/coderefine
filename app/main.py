import json
import re
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import BASE_DIR, JWT_SECRET_KEY
from app.database import get_db, init_db
from app.auth_service import hash_password, verify_password, create_access_token, authenticate_user
from app.services import groq_service, utils

# Ensure DB initialized on startup
init_db()

def is_valid_source_code(text: str) -> bool:
    """
    Validates if the input text looks like source code.
    Uses keywords and syntax tokens checks to filter plain conversation.
    """
    text_stripped = text.strip()
    if not text_stripped:
        return False
        
    keywords = {
        "def", "function", "fn", "import", "from", "include", "public", "class", 
        "struct", "void", "return", "if", "for", "while", "else", "elif", "except", 
        "try", "catch", "throw", "let", "const", "var", "int", "float", "char", "double",
        "println", "printf", "cout", "print", "console", "using", "namespace", "std",
        "System", "out"
    }
    
    # Check for programming keywords
    words = re.findall(r'\b\w+\b', text_stripped)
    matching_keywords = [w for w in words if w in keywords]
    
    # Check common syntax symbols
    syntax_tokens = ['{', '}', ';', '(', ')', '[', ']', '=', '+', '-', '*', '/', '<', '>', ':', '"', "'"]
    syntax_count = sum(text_stripped.count(t) for t in syntax_tokens)
    
    return len(matching_keywords) >= 1 or syntax_count >= 1

class CodeRefineRequestHandler(BaseHTTPRequestHandler):
    """
    Pure Python HTTP Request Handler serving both the static SPA frontend
    and the REST API endpoints.
    """
    
    def log_message(self, format, *args):
        # Override to log cleanly to stdout
        sys_stderr_write(f"[{self.log_date_time_string()}] {format % args}\n")

    def end_headers(self):
        # Add CORS headers automatically to every response
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle pre-flight CORS requests."""
        self.send_response(200)
        self.end_headers()

    def send_json(self, data: Any, status_code: int = 200):
        """Helper to send JSON response."""
        response_bytes = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def send_error_json(self, message: str, status_code: int = 400):
        """Helper to send error JSON format matching FastAPI detail format."""
        self.send_json({"detail": message}, status_code)

    def serve_static_file(self, filepath: Path, content_type: str):
        """Serves static files from local disk."""
        try:
            if not filepath.exists() or not filepath.is_file():
                self.send_error_json("Resource not found", 404)
                return
                
            # Verify file stays inside BASE_DIR to prevent path traversal
            resolved = filepath.resolve()
            if not str(resolved).startswith(str(BASE_DIR.resolve())):
                self.send_error_json("Access forbidden", 403)
                return
                
            with open(filepath, 'rb') as f:
                content = f.read()
                
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error_json(f"Static file error: {str(e)}", 500)

    def get_authenticated_user(self) -> Optional[Dict[str, Any]]:
        """Authenticates user based on Authorization header."""
        auth_header = self.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None
        token = auth_header[7:]
        return authenticate_user(token)

    def parse_json_body(self) -> Dict[str, Any]:
        """Reads and parses the JSON request body."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                return {}
            body_bytes = self.rfile.read(content_length)
            return json.loads(body_bytes.decode('utf-8'))
        except Exception:
            raise ValueError("Invalid JSON body")

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # 1. Serve SPA Index Page
        if path == "/" or path == "/index.html":
            index_path = BASE_DIR / "app" / "templates" / "index.html"
            self.serve_static_file(index_path, "text/html")
            return
            
        # 2. Serve Static Assets (/static/...)
        if path.startswith("/static/"):
            # Determine content type
            ext = os.path.splitext(path)[1].lower()
            mime = "text/plain"
            if ext == ".css":
                mime = "text/css"
            elif ext == ".js":
                mime = "application/javascript"
            elif ext == ".png":
                mime = "image/png"
            elif ext == ".jpg" or ext == ".jpeg":
                mime = "image/jpeg"
            elif ext == ".svg":
                mime = "image/svg+xml"
            elif ext == ".ico":
                mime = "image/x-icon"
                
            filepath = BASE_DIR / path.lstrip("/")
            self.serve_static_file(filepath, mime)
            return

        # ================= API ENDPOINTS =================
        try:
            # GET /api/auth/me
            if path == "/api/auth/me":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                # Mask key
                raw_key = user.get("groq_key")
                masked_key = ""
                if raw_key:
                    masked_key = f"sk-...{raw_key[-4:]}" if len(raw_key) > 4 else "sk-..."
                    
                self.send_json({
                    "id": user["id"],
                    "username": user["username"],
                    "has_groq_key": bool(raw_key),
                    "groq_key_masked": masked_key
                })
                return

            # GET /api/history
            if path == "/api/history":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT id, title, language, original_code, optimized_code, review_json, chat_json, created_at
                        FROM reviews
                        WHERE user_id = ?
                        ORDER BY created_at DESC
                        """,
                        (user["id"],)
                    )
                    rows = cursor.fetchall()
                    
                    history = []
                    for row in rows:
                        history.append({
                            "id": row["id"],
                            "title": row["title"],
                            "language": row["language"],
                            "original_code": row["original_code"],
                            "optimized_code": row["optimized_code"],
                            "review_json": json.loads(row["review_json"]),
                            "chat_history": json.loads(row["chat_json"]) if row["chat_json"] else [],
                            "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"] or "")
                        })
                self.send_json(history)
                return

            # Route not matched
            self.send_error_json("Not found", 404)
            
        except Exception as e:
            self.send_error_json(f"Server Error: {str(e)}", 500)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        try:
            data = self.parse_json_body()
        except ValueError as err:
            self.send_error_json(str(err), 400)
            return

        try:
            # POST /api/auth/register
            if path == "/api/auth/register":
                username = data.get("username", "").strip()
                password = data.get("password", "")
                
                if len(username) < 3 or len(password) < 4:
                    self.send_error_json("Username must be >= 3 and password >= 4 chars.", 400)
                    return
                    
                hashed = hash_password(password)
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Check duplicate user
                    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                    if cursor.fetchone():
                        self.send_error_json("Username already exists", 400)
                        return
                    
                    cursor.execute(
                        "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
                        (username, hashed)
                    )
                # Generate access token immediately for seamless auto-login
                access_token = create_access_token(data={"sub": username})
                self.send_json({"access_token": access_token, "token_type": "bearer"}, 201)
                return

            # POST /api/auth/login
            if path == "/api/auth/login":
                username = data.get("username", "").strip()
                password = data.get("password", "")
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id, username, hashed_password FROM users WHERE username = ?", (username,))
                    user = cursor.fetchone()
                    
                    if not user or not verify_password(password, user["hashed_password"]):
                        self.send_error_json("Incorrect username or password", 401)
                        return
                        
                access_token = create_access_token(data={"sub": user["username"]})
                self.send_json({"access_token": access_token, "token_type": "bearer"})
                return

            # POST /api/auth/settings
            if path == "/api/auth/settings":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                key_input = data.get("groq_key", "").strip()
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE users SET groq_key = ? WHERE id = ?", (key_input if key_input else None, user["id"]))
                self.send_json({"message": "Groq API Key saved successfully"})
                return

            # POST /api/review
            if path == "/api/review":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                code = data.get("code", "")
                language = data.get("language", "")
                review_id = data.get("review_id")
                
                if not code.strip():
                    self.send_error_json("Code cannot be empty", 400)
                    return
                    
                if not is_valid_source_code(code):
                    self.send_error_json("This is not code. Please enter valid source code.", 400)
                    return
                    
                try:
                    review_result = groq_service.review_code(
                        code=code,
                        language=language,
                        api_key=user.get("groq_key")
                    )
                    
                    # Store or update in database
                    with get_db() as conn:
                        cursor = conn.cursor()
                        is_update = False
                        if review_id:
                            # Verify if it is an empty session that we can overwrite
                            cursor.execute("SELECT id, original_code FROM reviews WHERE id = ? AND user_id = ?", (review_id, user["id"]))
                            existing = cursor.fetchone()
                            if existing and not existing["original_code"].strip():
                                is_update = True
                                
                        if is_update:
                            cursor.execute(
                                """
                                UPDATE reviews 
                                SET title = ?, language = ?, original_code = ?, optimized_code = ?, review_json = ?
                                WHERE id = ?
                                """,
                                (
                                    review_result.get("title", f"{language.capitalize()} Optimization"),
                                    language,
                                    code,
                                    review_result.get("optimized_code", code),
                                    json.dumps(review_result),
                                    review_id
                                )
                            )
                            inserted_id = review_id
                        else:
                            cursor.execute(
                                """
                                INSERT INTO reviews (user_id, title, language, original_code, optimized_code, review_json, chat_json)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    user["id"],
                                    review_result.get("title", f"{language.capitalize()} Optimization"),
                                    language,
                                    code,
                                    review_result.get("optimized_code", code),
                                    json.dumps(review_result),
                                    "[]"
                                )
                            )
                            inserted_id = cursor.lastrowid
                    
                    review_result["id"] = inserted_id
                    review_result["original_code"] = code
                    review_result["language"] = language
                    self.send_json(review_result)
                except Exception as e:
                    self.send_error_json(str(e), 500)
                return

            # POST /api/complexity
            if path == "/api/complexity":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                code = data.get("code", "")
                language = data.get("language", "")
                eli5 = data.get("eli5", False)
                
                if not code.strip():
                    self.send_error_json("Code cannot be empty", 400)
                    return
                    
                if not is_valid_source_code(code):
                    self.send_error_json("This is not code. Please enter valid source code.", 400)
                    return
                    
                try:
                    analysis = groq_service.analyze_complexity(
                        code=code,
                        language=language,
                        eli5=eli5,
                        api_key=user.get("groq_key")
                    )
                    self.send_json(analysis)
                except Exception as e:
                    self.send_error_json(str(e), 500)
                return

            # POST /api/explain-error
            if path == "/api/explain-error":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                code = data.get("code", "")
                logs = data.get("error_logs", "")
                eli5 = data.get("eli5", False)
                
                if not code.strip() and not logs.strip():
                    self.send_error_json("Code or logs must be provided", 400)
                    return
                    
                if code.strip() and not is_valid_source_code(code):
                    self.send_error_json("This is not code. Please enter valid source code.", 400)
                    return
                    
                try:
                    explanation = groq_service.explain_error(
                        code=code,
                        error_logs=logs,
                        eli5=eli5,
                        api_key=user.get("groq_key")
                    )
                    
                    # Add links
                    topics = explanation.get("search_topics", [])
                    resources = []
                    for topic in topics:
                        links = utils.generate_educational_links(topic)
                        resources.append({
                            "topic": topic,
                            "youtube": links["youtube"],
                            "geeksforgeeks": links["geeksforgeeks"]
                        })
                    explanation["resources"] = resources
                    self.send_json(explanation)
                except Exception as e:
                    self.send_error_json(str(e), 500)
                return

            # POST /api/screen-capture
            if path == "/api/screen-capture":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                image_data = data.get("image", "")
                if not image_data.startswith("data:image/"):
                    self.send_error_json("Invalid image data URL format", 400)
                    return
                    
                try:
                    # Decode base64
                    import base64
                    header, base64_str = image_data.split(",", 1)
                    mime_type = header.split(";")[0].replace("data:", "")
                    img_bytes = base64.b64decode(base64_str)
                    
                    analysis = groq_service.analyze_screen_capture(
                        image_bytes=img_bytes,
                        mime_type=mime_type,
                        api_key=user.get("groq_key")
                    )
                    
                    # Validate that the OCR/screenshot extracts valid code
                    original_code = analysis.get("original_code_snippet", "")
                    if not is_valid_source_code(original_code):
                        self.send_error_json("This is not code. Please enter valid source code.", 400)
                        return
                        
                    self.send_json(analysis)
                except Exception as e:
                    self.send_error_json(str(e), 500)
                return

            # POST /api/chat
            if path == "/api/chat":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                code = data.get("code", "")
                language = data.get("language")
                message = data.get("message", "")
                history = data.get("history", [])
                review_id = data.get("review_id")
                
                if code.strip() and not is_valid_source_code(code):
                    self.send_error_json("This is not code. Please enter valid source code.", 400)
                    return
                    
                try:
                    response_text = groq_service.chat_about_code(
                        code=code,
                        message=message,
                        history=history,
                        api_key=user.get("groq_key")
                    )
                    
                    if review_id:
                        # Reconstruct full history with the newly received assistant response
                        updated_history = list(history)
                        updated_history.append({"role": "model", "text": response_text})
                        with get_db() as conn:
                            cursor = conn.cursor()
                            # Check ownership and fetch title
                            cursor.execute("SELECT id, title FROM reviews WHERE id = ? AND user_id = ?", (review_id, user["id"]))
                            review = cursor.fetchone()
                            if review:
                                # If the review title is "Untitled Chat", let's update it to the first message!
                                if review["title"] == "Untitled Chat" and len(history) == 1:
                                    first_msg = message.strip()
                                    new_title = first_msg[:30] + ("..." if len(first_msg) > 30 else "")
                                    if language:
                                        cursor.execute(
                                            "UPDATE reviews SET chat_json = ?, title = ?, original_code = ?, language = ? WHERE id = ?",
                                            (json.dumps(updated_history), new_title, code, language, review_id)
                                        )
                                    else:
                                        cursor.execute(
                                            "UPDATE reviews SET chat_json = ?, title = ?, original_code = ? WHERE id = ?",
                                            (json.dumps(updated_history), new_title, code, review_id)
                                        )
                                else:
                                    if language:
                                        cursor.execute(
                                            "UPDATE reviews SET chat_json = ?, original_code = ?, language = ? WHERE id = ?",
                                            (json.dumps(updated_history), code, language, review_id)
                                        )
                                    else:
                                        cursor.execute(
                                            "UPDATE reviews SET chat_json = ?, original_code = ? WHERE id = ?",
                                            (json.dumps(updated_history), code, review_id)
                                        )
                                
                    self.send_json({"text": response_text})
                except Exception as e:
                    self.send_error_json(str(e), 500)
                return

            # POST /api/review/new
            if path == "/api/review/new":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                # Create a blank review record
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO reviews (user_id, title, language, original_code, optimized_code, review_json, chat_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user["id"],
                            "Untitled Chat",
                            "general",
                            "",
                            "",
                            "{}",
                            "[]"
                        )
                    )
                    new_id = cursor.lastrowid
                    
                self.send_json({
                    "id": new_id,
                    "title": "Untitled Chat",
                    "language": "general",
                    "original_code": "",
                    "optimized_code": "",
                    "review_json": {},
                    "chat_history": []
                }, 201)
                return

            # POST /api/review/update
            if path == "/api/review/update":
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                review_id = data.get("id")
                code = data.get("code", "")
                title = data.get("title")
                language = data.get("language")
                
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Check ownership
                    cursor.execute("SELECT id FROM reviews WHERE id = ? AND user_id = ?", (review_id, user["id"]))
                    if not cursor.fetchone():
                        self.send_error_json("Review item not found", 404)
                        return
                        
                    if title and language:
                        cursor.execute("UPDATE reviews SET original_code = ?, title = ?, language = ? WHERE id = ?", (code, title, language, review_id))
                    elif title:
                        cursor.execute("UPDATE reviews SET original_code = ?, title = ? WHERE id = ?", (code, title, review_id))
                    elif language:
                        cursor.execute("UPDATE reviews SET original_code = ?, language = ? WHERE id = ?", (code, language, review_id))
                    else:
                        cursor.execute("UPDATE reviews SET original_code = ? WHERE id = ?", (code, review_id))
                        
                self.send_json({"message": "Session updated successfully"})
                return

            # POST /api/review/copy/{id}
            match = re.match(r'^/api/review/copy/(\d+)$', path)
            if match:
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                review_id = int(match.group(1))
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Fetch original review
                    cursor.execute(
                        """
                        SELECT title, language, original_code, optimized_code, review_json
                        FROM reviews
                        WHERE id = ? AND user_id = ?
                        """,
                        (review_id, user["id"])
                    )
                    original = cursor.fetchone()
                    if not original:
                        self.send_error_json("Review item not found", 404)
                        return
                        
                    # Insert new copy with empty chat_json
                    cursor.execute(
                        """
                        INSERT INTO reviews (user_id, title, language, original_code, optimized_code, review_json, chat_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user["id"],
                            original["title"],
                            original["language"],
                            original["original_code"],
                            original["optimized_code"],
                            original["review_json"],
                            "[]"
                        )
                    )
                    new_id = cursor.lastrowid
                    
                self.send_json({
                    "id": new_id,
                    "title": original["title"],
                    "language": original["language"],
                    "original_code": original["original_code"],
                    "optimized_code": original["optimized_code"],
                    "review_json": json.loads(original["review_json"]),
                    "chat_history": []
                }, 201)
                return

            # Route not matched
            self.send_error_json("Not found", 404)

        except Exception as e:
            self.send_error_json(f"Server Error: {str(e)}", 500)

    def do_DELETE(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        try:
            # DELETE /api/history/{id}
            match = re.match(r'^/api/history/(\d+)$', path)
            if match:
                user = self.get_authenticated_user()
                if not user:
                    self.send_error_json("Could not validate credentials", 401)
                    return
                    
                review_id = int(match.group(1))
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Check ownership
                    cursor.execute("SELECT id FROM reviews WHERE id = ? AND user_id = ?", (review_id, user["id"]))
                    if not cursor.fetchone():
                        self.send_error_json("Review item not found", 404)
                        return
                        
                    cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
                self.send_json({"message": "Review history deleted successfully"})
                return

            self.send_error_json("Not found", 404)
        except Exception as e:
            self.send_error_json(f"Server Error: {str(e)}", 500)

def sys_stderr_write(msg: str):
    import sys
    sys.stderr.write(msg)
    sys.stderr.flush()

def run_server(host: str = "127.0.0.1", port: int = 8000):
    server_address = (host, port)
    httpd = HTTPServer(server_address, CodeRefineRequestHandler)
    print(f"CodeRefine HTTP Server running on http://{host}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CodeRefine Server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
