import subprocess
from multiprocessing import Queue

import numpy

from stream import StreamReader


class RTMPStream(StreamReader):

    def __init__(self, rtmpAddr: str):
        super().__init__(Queue())
        self.rtmpAddr = rtmpAddr
        self.pipe = None

    def onStart(self):
        self.pipe = subprocess.Popen(['ffmpeg',
                                      '-y',  # (optional) overwrite output file if it exists
                                      # '-loglevel', 'error',
                                      '-i', '-',  # The input comes from a pipe
                                      '-pix_fmt', 'rgb24',
                                      '-vcodec', 'h264_nvenc',
                                      '-an',  # Tells FFMPEG not to expect any audio
                                      '-f', 'flv',
                                      self.rtmpAddr]
                                     )

    def process(self, frame: numpy.ndarray):
        self.pipe.stdin.write(frame)
