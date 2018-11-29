import datetime
import os
import subprocess
from multiprocessing import Queue
from pathlib import Path

import numpy

from stream import StreamReader


class SaveFile(StreamReader):

    def __init__(self, filePath: Path, interval: int):
        """

        :param filePath: 文件夹前缀路径
        :param interval: 存储间隔
        """
        super().__init__(Queue(250))
        self.filePath = filePath
        self.pipe = None
        self.interval = interval
        self.count = 0

    def onStart(self):
        self.count = 0
        now = datetime.datetime.now()
        floder = Path(self.filePath, f"{now.year}/{now.month}/{now.day}")
        if not os.path.exists(floder):
            os.makedirs(floder)
        self.pipe = subprocess.Popen(['ffmpeg',
                                      #'-hwaccel', 'cuvid',
                                      '-f', 'rawvideo',
                                      '-s', '1920x1080',
                                      '-pix_fmt', 'rgb24',
                                      '-r', '25',
                                      '-i', '-',  # The input comes from a pipe
                                      '-an',  # Tells FFMPEG not to expect any audio
                                      '-vcodec', 'h264_nvenc',
                                      '-gpu', '1',
                                      #'-crf', '24',
                                      #'-me_method', 'umh',
                                      #'-me_range', '50',
                                      #'-rc-lookahead', '100',
                                      #'-f', 'mp4',
                                      str(Path(floder, f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')}.mp4"))],
                                     stdin=subprocess.PIPE,
                                     stdout=None,
                                     stderr=None,
                                     )

    def process(self, frame: numpy.ndarray):
        if self.count > self.interval:
            self.pipe.stdin.close()
            self.onStart()
        self.count += 1
        self.pipe.stdin.write(frame)


class RTMPStream(StreamReader):

    def __init__(self, rtmpAddr: str):
        super().__init__(Queue(250))
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
                                      '-an',  # Tells FFMPEG not to expect any audio
                                      '-vcodec', 'h264_nvenc',
                                      '-gpu', '1',
                                      '-crf', '24',
                                      '-me_method', 'umh',
                                      '-me_range', '50',
                                      '-rc-lookahead', '100',
                                      '-f', 'flv',
                                      self.rtmpAddr],
                                     stdin=subprocess.PIPE,
                                     stdout=None,
                                     stderr=None,
                                     )

    def process(self, frame: numpy.ndarray):
        # print(frame.size)
        self.pipe.stdin.write(frame)
