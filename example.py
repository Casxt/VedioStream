import time
from pathlib import Path

from reader import RTMPStream, SaveFile
from stream import Stream
print(1.2)
saveFile = SaveFile(Path("/data/zhangkai/VedioStream"), 2500)
rtmp = RTMPStream("rtmp://0.0.0.0:1935/live")
stream = Stream(input="rtsp://192.168.3.58", outputs=[rtmp, saveFile])
saveFile.start()
rtmp.start()

time.sleep(2)
stream.start()

rtmp.join()
