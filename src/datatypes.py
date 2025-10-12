import datetime

class User:
    uuid: int
    server_username: str
    global_username: str
    liable: int
    visible: int
    timeout: datetime.datetime
    def __init__(self, uuid: int, server_username: str = None, global_username: str = None, liable: int = 1, visible: int = 1, timeout: str = None):
        self.uuid = uuid
        self.server_username = server_username
        self.global_username = global_username
        self.liable = liable
        self.visible = visible
        if timeout:
            self.timeout = datetime.datetime.fromisoformat(timeout)
        else:
            self.timeout = None

class BranchMessage:
    message_id: int
    message_text: str
    read_time: datetime.datetime
    def __init__(self, message_id: int, message_text: str, read_time: datetime.datetime = None):
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
    mentioned_users: list[User]
    branch_messages: list[BranchMessage]
    guild_id: int | None = None
    def __init__(self, message_id: int, message_text: str,
                 disband: int = 0, read_time: str = None,
                 mentioned_users: list['User'] = None,
                 author: User = None,
                 channel_id: int | None = None, channel_name: str | None = None,
                 guild_id: int | None = None):
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

