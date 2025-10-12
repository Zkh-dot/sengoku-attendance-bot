import os
import sqlite3
from flask import Flask, g, render_template_string, url_for, abort

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
<h2>Мемберс</h2>
<table>
  <tr>
    <th>Мембер</th>
    <th>UID (ссылка)</th>
    <th>Посетил контентов</th>
    <th>Сумма очков</th>
  </tr>
  {% for row in rows %}
    <tr>
      <td>{{ row['display_name'] or '—' }}</td>
      <td><a href='{{ url_for('user_detail', uid=row['uid']) }}'>{{ row['uid'] }}</a></td>
      <td>{{ row['event_count'] }}</td>
      <td>{{ row['total_points'] or 0 }}</td>
    </tr>
  {% endfor %}
</table>
"""

USER_HTML = """
<h2>Посещенные контенты</h2>
<table>
  <tr>
    <th>Кол</th>
    <th>Канал</th>
    <th>Бот увидел</th>
    <th>Дизбанд (✗ / ✓)</th>
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
               COALESCE(NULLIF(u.global_username, ''), u.server_username) AS display_name,
               COUNT(DISTINCT CASE WHEN e.disband != 1 THEN e.message_id END) AS event_count,
               COALESCE(SUM(CASE WHEN e.disband != 1 THEN e.points ELSE 0 END), 0) AS total_points
        FROM USERS u
        LEFT JOIN EVENTS_TO_USERS etu ON etu.ds_uid = u.uid
        LEFT JOIN EVENTS e ON e.message_id = etu.message_id
        GROUP BY u.uid
        ORDER BY total_points DESC, event_count DESC, display_name COLLATE NOCASE ASC
    """)
    rows = q.fetchall()
    html = render_template_string(INDEX_HTML, rows=rows)
    return render_template_string(BASE_HTML, title='Мемберсы vs Посещения', subtitle=f'Всего мемберсов: {len(rows)}', content=html)

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
    return render_template_string(BASE_HTML, title=f"{user['display_name'] or 'без имени'}", subtitle=f"Сходил на {len(events)} контента (✓ — проведенные, ✗ — дизбанднутые)", content=html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
