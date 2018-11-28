from reader import RTMPStream
from stream import Stream

rtmp = RTMPStream("rtmp://0.0.0.0:1935/live")
stream = Stream(input="rtsp://192.168.3.58", outputs=[rtmp])
rtmp.start()
stream.start()

rtmp.join()
