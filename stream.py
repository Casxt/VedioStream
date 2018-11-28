import time
from multiprocessing import Process, Queue

import cv2
import numpy


class Stream(Process):
    """
    接受一条视频流, 解析并将帧发送给处理函数
    """

    def __init__(self, input: str, outputs: list):
        """
        :param input: 输入流
        :param output: 输出流
        """
        super().__init__()
        self.daemon = True
        self.input = input
        assert all(issubclass(type(o), StreamReader) for o in outputs)
        self.outputs = outputs
        self.video, self.fps, self.size = None, None, None

    def run(self):
        # get video info
        self.video = cv2.VideoCapture(self.input)
        self.fps = self.video.get(cv2.CAP_PROP_FPS)
        self.size = (
            self.video.get(cv2.CAP_PROP_FRAME_WIDTH), self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))

        while self.video.isOpened() and self.video.grab():
            startTime = time.time()

            ret, frame = self.video.retrieve()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            for output in self.outputs:
                output.stream.put(frame)
            usedTime = time.time() - startTime
            sleepTime = 1 / self.fps - usedTime
            time.sleep(sleepTime if sleepTime > 0 else 0)


class StreamReader(Process):
    """
    用于处理Stream的回调
    """

    def __init__(self, stream: Queue):
        super().__init__()
        self.daemon = True
        self.stream = stream

    def onStart(self):
        """用于在另一线程初始化"""
        pass
    def process(self, frame: numpy.ndarray):
        """用于在另一线程获取数据, frame 格式为rgb24"""
        pass

    def run(self):
        assert self.stream is not None
        self.onStart()
        while True:
            frame: numpy.ndarray = self.stream.get()
            self.process(frame)

