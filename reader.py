import subprocess
from multiprocessing import Queue

import numpy

from stream import StreamReader


class RTMPStream(StreamReader):

    def __init__(self, rtmpAddr: str):
        super().__init__(Queue(25))
        self.rtmpAddr = rtmpAddr
        self.pipe = None

    def onStart(self):
        self.pipe = subprocess.Popen(['ffmpeg',
                                      '-hwaccel', 'cuvid',
                                      '-f', 'rawvideo',
                                      '-s', '1920x1080',
                                      '-pix_fmt', 'rgb24',
                                      '-r', '25',
                                      '-i', '-',  # The input comes from a pipe
                                      '-vcodec', 'h264_nvenc',
                                      '-an',  # Tells FFMPEG not to expect any audio
                                      '-gpu', '1',
                                      '-crf', '24',
                                      '-me_method', 'umh',
                                      '-me_range', '50',
                                      '-rc-lookahead', '100',
                                      '-f', 'flv',
                                      self.rtmpAddr],
                                     stdin=subprocess.PIPE
                                     )

    def process(self, frame: numpy.ndarray):
        # print(frame.size)
        self.pipe.stdin.write(frame)
