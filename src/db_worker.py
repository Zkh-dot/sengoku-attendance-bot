import sqlite3
import datetime
import datatypes
import os
import pandas as pd
class DBWorker:
    def __init__(self, db_path: str = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'sengoku_bot.db'
        )):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
CREATE TABLE IF NOT EXISTS USERS (
    uid INTEGER PRIMARY KEY,
    server_username TEXT,
    global_username TEXT,
    liable INTEGER,
    visible INTEGER,
    timeout DATETIME,
    need_to_get INTEGER DEFAULT 45,
    is_member INTEGER DEFAULT 1,
    join_date DATETIME,
    roles TEXT
);
        ''')
        self.cursor.execute('''
CREATE TABLE IF NOT EXISTS EVENTS_TO_USERS (
    ds_uid INTEGER,
    message_id INTEGER,
    PRIMARY KEY (ds_uid, message_id),
    FOREIGN KEY (ds_uid) REFERENCES USERS(uid),
    FOREIGN KEY (message_id) REFERENCES EVENTS(message_id)
);
        ''')
        self.cursor.execute('''
CREATE TABLE IF NOT EXISTS EVENTS (
    message_id INTEGER PRIMARY KEY,
    author_user_id INTEGER,
    message_text TEXT,
    disband INTEGER,
    read_time DATETIME,
    channel_id INTEGER,
    channel_name TEXT,
    guild_id INTEGER,
    points INTEGER DEFAULT 0,
    hidden INTEGER DEFAULT 0,
    usefull_event INTEGER DEFAULT 0,
    FOREIGN KEY (author_user_id) REFERENCES USERS(uid)
);
        ''')
        self.cursor.execute('''
CREATE TABLE IF NOT EXISTS BRANCH_MESSAGES (
    message_id INTEGER PRIMARY KEY,
    parent_message_id INTEGER,
    message_text TEXT,
    read_time DATETIME,
    FOREIGN KEY (parent_message_id) REFERENCES EVENTS(message_id)
);
''')

    def execute(self, query: str, params: tuple = ()):
        self.cursor.execute(query, params)
        self.conn.commit()
        return self.cursor

    def fetchall(self, query: str, params: tuple = ()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def fetchone(self, query: str, params: tuple = ()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()

    def close(self):
        self.conn.close()

    def get_user_info(self) -> list[datatypes.User]:
        data = self.cursor.execute("""
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
        return data.fetchall()
    
    def load_database_as_dataframe(self) -> pd.DataFrame:
        data = self.get_user_info()
        columns = ['uid', 'display_name', 'liable', 'event_count', 'total_points', 'need_to_get', 'is_member']
        df = pd.DataFrame(data, columns=columns)
        return df

    def add_user(self, user: datatypes.User):
        self.execute('''
INSERT OR REPLACE INTO USERS (
                     uid,
                     server_username,
                     global_username,
                     liable,
                     visible,
                     timeout,
                     need_to_get,
                     is_member,
                     join_date,
                     roles
                    )
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
        user.uuid,
        user.server_username,
        user.global_username,
        user.liable,
        user.visible,
        user.timeout.isoformat() if user.timeout else None,
        user.need_to_get,
        user.is_member,
        user.join_date.isoformat() if user.join_date else None,
        user.roles
    ))
        
    def add_branch_message(self, branch_message: datatypes.BranchMessage, parent_message_id: int):
        self.execute('''
INSERT OR REPLACE INTO BRANCH_MESSAGES (message_id, parent_message_id, message_text, read_time)
VALUES (?, ?, ?, ?)
''', (branch_message.message_id, parent_message_id, branch_message.message_text, branch_message.read_time.isoformat() if branch_message.read_time else None))
        
    def add_event_user_link(self, user_id: int, message_id: int):
        self.execute('''
INSERT OR REPLACE INTO EVENTS_TO_USERS (ds_uid, message_id)
VALUES (?, ?)
''', (user_id, message_id))

    def add_event(self, event: datatypes.Event):
        self.add_user(event.author)
        self.execute('''
INSERT OR REPLACE INTO EVENTS (message_id, author_user_id, message_text, disband, read_time, channel_id, channel_name, guild_id, points, hidden, usefull_event)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
        event.message_id,
        event.author.uuid,
        event.message_text,
        event.disband,
        event.read_time.isoformat() if event.read_time else None,
        event.channel_id,
        event.channel_name,
        event.guild_id,
        event.points,
        1 if event.hidden else 0,
        1 if event.usefull_event else 0
        ))
        for mu in event.mentioned_users:
            self.add_user(mu)
        for bm in event.branch_messages:
            self.add_branch_message(bm, event.message_id)
        for mu in event.mentioned_users:
            self.add_event_user_link(mu.uuid, event.message_id)

    def get_user(self, uid: int) -> datatypes.User | None:
        row = self.fetchone('SELECT * FROM USERS WHERE uid=?', (uid,))
        if row:
            return datatypes.User(
                uuid=row[0],
                server_username=row[1],
                global_username=row[2],
                liable=row[3],
                visible=row[4],
                timeout=row[5]
            )
        return None