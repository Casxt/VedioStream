# 简介
基于opencv读取视频/视频流, 并逐帧传输至Reader

# 关键特性
多进程处理, Reader之间互不阻塞

# 使用方法
## 视频转RTMP服务器示例
### 创建`StreamReader`的子类
- `__init__`方法中给父类传入一个Queue, 建议设置一个较小的长度, 否则可能导致内存不足等问题
- `onStart`方法中写入用于初始化的语句, 如果不需要也可以不写, 示例中我们在此处开启smtp服务
- `process`方法将会在收到图片时被调用, 传入的图片格式为一维ndarray, 长度为`h*w*channel`, 其为opencv所读出的图像
```python
ret, frame = video.read()
frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
```
所以一个完整的类应为:
```python
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
                                      '-vcodec', 'libx264',
                                      '-an',  # Tells FFMPEG not to expect any audio
                                      '-gpu', '1',
                                      '-crf', '24',
                                      '-f', 'flv',
                                      self.rtmpAddr],
                                     stdin=subprocess.PIPE
                                     )

    def process(self, frame: numpy.ndarray):
        self.pipe.stdin.write(frame)
```
### 注册reader, 开启视频流
- 创建子类实例
- 指定`Stream`输入地址或文件, 将子类实例传入, 应注意其输入是一个数组, 可以输入多个reader, `Stream`读取的视频帧会尝试传给每一个reader
```python
rtmp = RTMPStream("rtmp://0.0.0.0:1935/live")
stream = Stream(input="rtsp://192.168.3.58", outputs=[rtmp])
```

### 启动
- 启动所有的reader和stream即可, 要确保所有的reader启动后才能启动stream
```python
rtmp.start()
stream.start()
```