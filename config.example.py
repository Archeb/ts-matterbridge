speech_config = dict(
    subscription="",  # Azure Speech API Token
    region="japaneast"  # Azure Speech API Region
)
audiobot_config = dict(
    api="http://127.0.0.1:58913/api",  # TSAudioBot HTTP API Address
    auth_header={
        'Authorization': 'Basic XXXXXXXXXXXXXXXXXXXXXX'}  # TSAudioBot HTTP API Token (Base64)
)
matterbridge_config = dict(
    api="http://127.0.0.1:50819/api",  # MatterBridge HTTP API Address
    authToken="",
    gateway=""
)
teamspeak_config = dict(
    server="",  # TeamSpeak Server Address
    port=10003,  # TeamSpeak Server Query Port (You should add an IP whitelist for this bot)
    nick="Bridge_Bot",  # Bot's Nickname, won't be shown in the channel client list
    username="serveradmin",  # Server Query Username
    password=""  # Server Query Password
)
