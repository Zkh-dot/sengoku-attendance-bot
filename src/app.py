import os
import sqlite3
from flask import Flask, g, render_template_string, url_for, abort
import dotenv
dotenv.load_dotenv()

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", "./sengoku_bot.db")

BASE_HTML = """
<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <title>{{ title }}</title>
  <style>
    body {
      background-color: #1e1e1e;
      color: #e0e0e0;
      font-family: Arial, sans-serif;
      text-align: center;
      margin: 0;
      padding: 20px;
    }
    h1, h2 { color: #ffffff; }
    p { color: #bbbbbb; }
    table {
      margin: 0 auto;
      border-collapse: collapse;
      width: 80%;
      background-color: #2a2a2a;
      border: 1px solid #444;
    }
    th, td {
      border: 1px solid #555;
      padding: 10px;
      text-align: left;
    }
    th {
      background-color: #333;
    }
    tr:nth-child(even) { background-color: #242424; }
    tr:hover { background-color: #383838; }
    a { color: #7aa2f7; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .highlight { color: #00ff88; font-weight: bold; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p>{{ subtitle }}</p>
  {{ content|safe }}
</body>
</html>
"""

INDEX_HTML = """
<h2>Подсчет ведется с отставанием в 24 часа, т.е. сейчас посещения за сегодня не отображаются.</h2>
<h2>Список пользователей</h2>
<h3>Легенда по цветам:</h3>
<ul style="list-style-type:none; padding:0;">
  <li><span style="color:#00bfff; font-weight:bold;">Голубой</span> — не требуется набирать очки</li>
  <li><span style="color:#888888; font-weight:bold;">Серый</span> — ливнул</li>
  <li><span style="color:#00ff88; font-weight:bold;">Зелёный</span> — молодец</li>
  <li><span style="color:#ffff00; font-weight:bold;">Жёлтый</span> — почти молодец (набрал ≥50% от цели)</li>
  <li><span style="color:#e0e0e0; font-weight:bold;">Белый</span> — всё остальное</li>
  <li><span style="color:#ffa500; font-weight:bold;">Оранжевый</span> — ментор</li>
  <li><span style="color:#be03fc; font-weight:bold;">Фиолетовый</span> — рекрутер</li>
  <li><span style="color:#fc0303; font-weight:bold;">Красный</span> — офицер</li>
</ul>
<ul style="list-style-type:none; padding:0;">
  <td><a href='https://discordapp.com/channels/1355240968621658242/1369330940551106665' target='_blank'>📗┆правила-посещения</a></td>
</ul>
<table>
  <tr>
    <th>Пользователь</th>
    <th>UID (ссылка)</th>
    <th>Количество активных ивентов</th>
    <th>Сумма очков</th>
    <th>Цель (нужно очков)</th>
    <tr style="color: #310036; font-weight: bold; background-color: #999;">
      <td>D9dka</td>
      <td>—</td>
      <td>∞</td>
      <td>∞</td>
      <td>0</td>
    </tr>
    {% for row in rows %}
      {% set color = '' %}
      {% if row['liable'] == 0 %}
        {% set color = '#00bfff' %} {# голубой #}
      {% elif row['liable'] == 2 %}
        {% set color = '#fc0303' %} {# красный #}
      {% elif row['liable'] == 3 %}
        {% set color = '#ffa500' %} {# оранжевый #}
      {% elif row['liable'] == 4 %}
        {% set color = '#be03fc' %} {# фиолетовый #}
      {% elif row['is_member'] == 0 %}
        {% set color = '#888888' %} {# серый #}
      {% elif row['total_points'] >= row['need_to_get'] %}
        {% set color = '#00ff88' %} {# зелёный #}
      {% elif row['total_points'] >= row['need_to_get'] * 0.5 %}
        {% set color = '#ffff00' %} {# жёлтый #}
      {% endif %}
      <tr style="color: {{ color if color else '#e0e0e0' }}">
        <td>{{ row['display_name'] or '—' }}</td>
        <td><a href='{{ url_for('user_detail', uid=row['uid']) }}'>{{ row['uid'] }}</a></td>
        <td>{{ row['event_count'] }}</td>
        <td>{{ row['total_points'] or 0 }}</td>
        <td>{{ row['need_to_get'] }}</td>
      </tr>
    {% endfor %}
</table>
"""

USER_HTML = """
<h2>Ивенты пользователя</h2>
<table>
  <tr>
    <th>Сообщение</th>
    <th>Канал</th>
    <th>Прочитано</th>
    <th>Отмена (✗ / ✓)</th>
    <th>Очки</th>
    <th>Ссылка</th>
  </tr>
  {% for e in events %}
    <tr>
      <td>{{ (e['message_text'] or '')[:100] }}</td>
      <td>{{ e['channel_name'] or '—' }}</td>
      <td>{{ e['read_time'] or '—' }}</td>
      <td style="text-align:center; font-weight:bold;">{% if e['disband'] == 1 %}✗{% else %}✓{% endif %}</td>
      <td>{{ e['points'] or 0 }}</td>
      <td><a href='https://discord.com/channels/{{ e['guild_id'] }}/{{ e['channel_id'] }}/{{ e['message_id'] }}' target='_blank'>Открыть</a></td>
    </tr>
  {% endfor %}
</table>
"""

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db = get_db()
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
    html = render_template_string(INDEX_HTML, rows=rows)
    return render_template_string(BASE_HTML, title='Пользователи × ивенты', subtitle=f'Всего пользователей: {len(rows)}', content=html)

@app.route('/user/<int:uid>')
def user_detail(uid):
    db = get_db()
    uq = db.execute("SELECT uid, COALESCE(NULLIF(global_username, ''), server_username) AS display_name FROM USERS WHERE uid=?", (uid,))
    user = uq.fetchone()
    if not user:
        abort(404)
    eq = db.execute("""
        SELECT e.message_id, e.guild_id, e.channel_id, e.channel_name, e.message_text, e.read_time, e.disband, e.points
        FROM EVENTS_TO_USERS etu
        JOIN EVENTS e ON e.message_id = etu.message_id
        WHERE etu.ds_uid = ?
        ORDER BY e.message_id DESC
    """, (uid,))
    events = eq.fetchall()
    html = render_template_string(USER_HTML, events=events)
    return render_template_string(BASE_HTML, title=f"{user['display_name'] or 'без имени'}", subtitle=f"Сходил на {len(events)} ивентов (✓ — активные, ✗ — отменённые)", content=html)

# Respect reverse-proxy headers and prefix
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
