import datetime

class User:
    uuid: int
    server_username: str
    global_username: str
    liable: int
    visible: int
    timeout: datetime.datetime
    need_to_get: int
    is_member: int = 1
    join_date: datetime.datetime
    def __init__(self,
                uuid: int,
                server_username: str = None,
                global_username: str = None,
                liable: int = 1,
                visible: int = 1,
                timeout: str = None,
                need_to_get: int = 45,
                is_member: int = 1,
                join_date: datetime.datetime = None):
        self.uuid = uuid
        self.server_username = server_username
        self.global_username = global_username
        self.liable = liable
        self.visible = visible
        self.need_to_get = need_to_get
        self.is_member = is_member
        self.join_date = join_date
        if timeout:
            self.timeout = datetime.datetime.fromisoformat(timeout)
        else:
            self.timeout = None

class BranchMessage:
    message_id: int
    message_text: str
    read_time: datetime.datetime
    def __init__(self,
                message_id: int,
                message_text: str,
                read_time: datetime.datetime = None):
        self.message_id = message_id
        self.message_text = message_text
        if read_time:
            self.read_time = read_time
        else:
            self.read_time = None

class Event:
    message_id: int
    author: User
    message_text: str
    disband: int
    read_time: datetime.datetime
    channel_id: int
    channel_name: str
    points: int = 0
    mentioned_users: list[User]
    branch_messages: list[BranchMessage]
    hidden: bool = False
    guild_id: int | None = None
    def __init__(self,
                message_id: int,
                message_text: str,
                 disband: int = 0,
                read_time: str = None,
                 mentioned_users: list['User'] = None,
                 author: User = None,
                 channel_id: int | None = None,
                channel_name: str | None = None,
                 guild_id: int | None = None,
                 points: int = 0,
                 hidden: bool = False):
        self.message_id = message_id
        self.message_text = message_text
        self.disband = disband
        self.author = author
        self.read_time = read_time if read_time else datetime.datetime.now(datetime.timezone.utc)
        self.mentioned_users = mentioned_users or []
        self.branch_messages = []
        self.channel_id = channel_id
        self.channel_name = channel_name
        self.guild_id = guild_id
        self.points = points
        self.hidden = hidden
