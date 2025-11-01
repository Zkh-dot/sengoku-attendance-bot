import dotenv
import os
from datetime import date
dotenv.load_dotenv()

GUILD_IDS = {1355240968621658242}
DISBAND_MESSAGES = {'дизбанд', 'диз', 'disband', 'dis'}
TREASURY_MESSAGES = {'казну', 'казна'}
FROM_HOURS = 26
TO_HOURS = 23
NAME_LINE = r".*?<@&?(.*?)>.*?"
REACTION_YES = '✅'
REACTION_NO = '❌'
MIN_USERS = 4
TREASURY_POINTS = 15
CHANNELS = {
    1355377613459161148: 3, # lfg
    1355377675845505034: 3, # pvp
    1355377776810659980: 3, # pve
    1355377711979302993: 3, # gang
    1389934518403731507: 2, # group-maps
    1355377749828567040: 3, # ava-dungeon
    1363140680985346242: 5, # zvz 12 utc
    1397112047803699311: 5, # zvz 14 utccommon
    1397112122021773334: 5, # zvz 16 utc
    1397112176522559582: 5, # zvz 18 utc
    1419352914258038805: 5, # zvz fast mass
}
HIDDEN = {
    1345611337559965737: 3, # gru-morning
    1345611509127970906: 3, # gru-day
    1345611851026792500: 3, # gru-evening
    1345611986033180683: 3, # gru-night
}
POINTS_GROUP_MAP = 2
RENTOR_NAME = 'Rentor'
GROUP_MAP_NAMES = ['группики', 'групики', 'карты']
REACT_TO_MESSAGES = os.getenv("REACT_TO_MESSAGES")
if REACT_TO_MESSAGES is None:
    REACT_TO_MESSAGES = True
else:
    REACT_TO_MESSAGES = str(REACT_TO_MESSAGES).strip().lower() in ("1", "true", "yes", "y", "on")

ADMIN_ROLES = {
    "Rentor": 0,
    "Officer": 2,
    "Mentor": 3,
    "Recruiter": 4
}
TODAY = date.today()