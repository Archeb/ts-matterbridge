from operator import truediv
import os
import time
import json
import random
import config
import requests
import traceback
import azure.cognitiveservices.speech as speechsdk

from MatterBridgeConnection import MatterBridgeConnection
from TSConnection import TSConnection

TYPE = 0
FROM = 1
TEXT = 3

speech_config = speechsdk.SpeechConfig(**config.speech_config)
synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
last_speech_time = 0
audiobot_api = config.audiobot_config["api"]
audiobot_auth_header = config.audiobot_config["auth_header"]

bridge = MatterBridgeConnection(**config.matterbridge_config)
bridge.run()

ts = TSConnection(**config.teamspeak_config)
ts.run()


def build_message(event):
    print(event)

    if not event:
        return None

    if event[TYPE] == "MSG":
        return "<%s> %s" % (event[1], event[3])
    elif event[TYPE] == "ACTION":
        return "* %s %s" % (event[1], event[3])
    elif event[TYPE] == "CONNECT":
        # return "*** %s connected ***" % ( event[1], )
        return "*** %s 进入了 TeamSpeak 服务器 ***" % (event[1], )
    elif event[TYPE] == "MOVE":
        # return "*** %s moved from [%s] to [%s] ***" % (event[1], event[2], event[3])
        return "*** %s 从频道 [%s] 跑到了频道 [%s] ***" % (event[1], event[2], event[3])
    elif event[TYPE] == "QUIT":
        # return "*** %s disconnected ***" % (event[1], )
        return "*** %s 离开了 TeamSpeak 服务器 ***" % (event[1], )
    else:
        return None


def get_ssml(text):
    available_voice = ['XiaoxuanNeural', 'XiaomoNeural']
    ssml_string = """<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
        xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
        <voice name="zh-CN-{0}">
            <mstts:silence  type="Sentenceboundary" value="1000ms"/>
            <mstts:express-as role="Girl" style="disgruntled">
                <prosody pitch="high" rate="1.1">
                    {1}
                </prosody>
            </mstts:express-as>
        </voice>
    </speak>"""
    return ssml_string.format(random.choice(available_voice), text)


while bridge.running() and ts.running():

    try:
        im = bridge.poll()
        tm = ts.poll()

        if (im and len(im[TEXT]) > 0):
            print(im)
            if(im[TYPE] == "MSG"):
                # print(im)
                ts.relay_message("(" + im[2] + ")",
                                 "<%s> %s" % (im[FROM], im[TEXT]))
            elif(im[TYPE == "GLOBALMSG"]):
                if(im[TEXT] == "getinfo"):
                    ts_user = ts.client_map()
                    ts_channel = ts.channel_map()
                    message = ""
                    for channel in ts_channel.items():
                        if len(channel[1]["members"]) > 0:
                            message += "\r\n" + ts.get_channel_name_with_relation(channel[1]) + ":"
                            for member in channel[1]["members"]:
                                message += " [" + ts_user[member]["client_nickname"] + "]"

                    bridge.send_text(message)
                    continue

                ts.relay_global_message(
                    "(" + im[2] + ")", "<%s> %s" % (im[FROM], im[TEXT]))

                if len(im[TEXT]) < 51:
                    speech_result = synthesizer.speak_ssml_async(
                        get_ssml(im[TEXT])).get()
                    speech_stream = speechsdk.AudioDataStream(speech_result)
                    speech_filename = os.getcwd() + "\\speechtemp\\" + \
                        str(int(round(time.time() * 1000))) + ".wav"
                    speech_stream.save_to_wav_file(speech_filename)
                    time.sleep(0.5)
                    try:
                        print(requests.get(audiobot_api + "/bot/use/0/(/json/merge/(/play/%s)/(/whisper/all))" %
                              (requests.utils.quote(speech_filename),), headers=audiobot_auth_header, timeout=1).text)
                    except:
                        print(traceback.format_exc())
                    last_speech_time = int(time.time())
                else:
                    #bridge.send_text("This passage exceeds 50 words limitation and will not be broadcast")
                    bridge.send_text("这段话超过50字，将不会有语音广播")
        if tm:
            print(tm)
            if (tm[TYPE] == "MSG"):
                bridge.relay_message(tm[FROM], tm[TEXT])
            else:
                bridge.send_text(build_message(tm))

        # time.sleep(0.1)
    except KeyboardInterrupt:
        bridge.disconnect()
        ts.disconnect()
