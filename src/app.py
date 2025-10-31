import os
import sqlite3
import re
from flask import Flask, g, render_template_string, request, url_for, abort
import dotenv
dotenv.load_dotenv()

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'sengoku_bot.db'
  ))

ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'archives')

with open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'static', 'base.html'
)) as f:
    BASE_HTML = f.read()

with open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'static', 'index.html'
)) as f:
    INDEX_HTML = f.read()

with open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'static', 'user.html'
)) as f:
    USER_HTML = f.read()

with open(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'static', 'timeout.html'
)) as f:
    TECHNICAL_TIMEOUT_HTML = f.read()

def get_archives():
    if not os.path.exists(ARCHIVE_DIR):
        return []
    files = [f for f in os.listdir(ARCHIVE_DIR) if f.endswith('.db')]
    archives = []
    for f in files:
        base = f[:-3]
        if re.match(r'^[a-z]+_\d{4}$', base):
            parts = base.split('_')
            month, year = parts
            name = f"{month.capitalize()} {year}"
            archives.append({'file': base, 'name': name})
    archives.sort(key=lambda x: x['file'], reverse=True)
    return archives

def get_db(db_path=None):
    # Use a cache dictionary inside g
    if not hasattr(g, '_db_cache'):
        g._db_cache = {}

    key = db_path or "default"
    if key not in g._db_cache:
        path = db_path or DB_PATH
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        g._db_cache[key] = conn

    return g._db_cache[key]

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db_param = request.args.get('db')
    db_path = None
    history_title = None
    if db_param:
        # Validate to prevent path traversal
        if not re.match(r'^[a-z]+_\d{4}$', db_param):
            abort(404)
        db_path = os.path.join(ARCHIVE_DIR, f"{db_param}.db")
        if not os.path.exists(db_path):
            abort(404)
        history_title = ' '.join([word.capitalize() for word in db_param.split('_')])
    
    if os.getenv("TECHNICAL_TIMEOUT", "0") == "1":
        return render_template_string(TECHNICAL_TIMEOUT_HTML + "<body><h1>Ведутся технические работы</h1><p>Извините за неудобства, скоро всё починим.</p></body></html>")
    
    db = get_db(db_path)
    q = db.execute("""
      SELECT u.uid,
           COALESCE(NULLIF(u.server_username, ''), u.global_username) AS display_name,
           u.liable,
           COUNT(DISTINCT CASE WHEN e.disband != 1 THEN e.message_id END) AS event_count,
           COALESCE(SUM(CASE WHEN e.disband != 1 THEN e.points ELSE 0 END), 0) AS total_points,
           u.need_to_get,
           u.is_member
      FROM USERS u
      LEFT JOIN EVENTS_TO_USERS etu ON etu.ds_uid = u.uid
      LEFT JOIN EVENTS e ON e.message_id = etu.message_id
      WHERE COALESCE(NULLIF(u.server_username, ''), u.global_username) != 'D9dka'
      GROUP BY u.uid
      ORDER BY total_points DESC, event_count DESC, display_name COLLATE NOCASE ASC
    """)
    rows = q.fetchall()
    
    archives = get_archives()
    
    subtitle = f'Всего мемберов: {len(rows)}'
    if history_title:
        subtitle = f'Historical Data: {history_title} | {subtitle}'
    
    html = render_template_string(INDEX_HTML, rows=rows, db_param=db_param)
    return render_template_string(BASE_HTML, title='мемберы × контент', subtitle=subtitle, content=html, archives=archives, db_param=db_param)


@app.route('/user/<int:uid>')
def user_detail(uid):
    db_param = request.args.get('db')
    db_path = None
    history_title = None
    if db_param:
        if not re.match(r'^[a-z]+_\d{4}$', db_param):
            abort(404)
        db_path = os.path.join(ARCHIVE_DIR, f"{db_param}.db")
        if not os.path.exists(db_path):
            abort(404)
        history_title = ' '.join([word.capitalize() for word in db_param.split('_')])
    
    db = get_db(db_path)
    uq = db.execute("SELECT uid, COALESCE(NULLIF(global_username, ''), server_username) AS display_name FROM USERS WHERE uid=?", (uid,))
    user = uq.fetchone()
    if not user:
        abort(404)
    eq = db.execute("""
        SELECT e.message_id, e.guild_id, e.channel_id, e.channel_name, e.message_text, e.read_time, e.disband, e.points, e.hidden
        FROM EVENTS_TO_USERS etu
        JOIN EVENTS e ON e.message_id = etu.message_id
        WHERE etu.ds_uid = ?
        ORDER BY e.message_id DESC
    """, (uid,))
    events = eq.fetchall()
    for i in range(len(events)):
        if events[i]['hidden']:
            events[i] = dict(events[i])
            events[i]['channel_name'] = f"None"
            events[i]['message_text'] = "А тебя это ебать не должно"
            events[i]['channel_id'] = 0
            events[i]['message_id'] = 0
            events[i]['guild_id'] = 0
    
    archives = get_archives()
    
    subtitle = f"Сходил на {len(events)} контентов (✓ — проведенные, ✗ — дизбанднутые)"
    if history_title:
        subtitle = f"{subtitle} (Historical: {history_title})"
    
    html = render_template_string(USER_HTML, events=events, db_param=db_param)
    return render_template_string(BASE_HTML, title=f"{user['display_name'] or 'без имени'}", subtitle=subtitle, content=html, archives=archives, db_param=db_param)


from werkzeug.middleware.proxy_fix import ProxyFix

class PrefixMiddleware:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        prefix = environ.get('HTTP_X_SCRIPT_NAME') or environ.get('HTTP_X_FORWARDED_PREFIX')
        if prefix:
            prefix = prefix.rstrip('/')
            environ['SCRIPT_NAME'] = prefix
            path = environ.get('PATH_INFO', '')
            if path.startswith(prefix):
                environ['PATH_INFO'] = path[len(prefix):] or '/'
        return self.app(environ, start_response)

# apply middlewares
app.wsgi_app = PrefixMiddleware(app.wsgi_app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
