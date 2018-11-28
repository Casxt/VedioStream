import datetime
import os
import subprocess
import time
from queue import Queue
from threading import Thread, Event, Lock

import cv2
import psycopg2
from PIL import Image

from model import *

FFMPEG_BIN = "ffmpeg"
camera_init_mutex = Lock()


class PerfLogger:
    """日志输出类"""

    def __init__(self):
        self.perf = {}

    def enter(self, name):
        if not name in self.perf:
            self.perf[name] = {
                'count': 0,
                'begin': datetime.datetime.now(),
                'total': datetime.timedelta(0, 0, 0)
            }
        item = self.perf[name]
        item['count'] += 1
        item['begin'] = datetime.datetime.now()

    def exit(self, name):
        item = self.perf[name]
        item['total'] += datetime.datetime.now() - item['begin']
        if datetime.datetime.now().second % 60 == 0:
            print(self)

    def __str__(self):
        return '\n'.join(['%s total: %s / %d = %s' % (
            k, self.perf[k]['total'], self.perf[k]['count'], self.perf[k]['total'] / self.perf[k]['count']) for k in
                          self.perf.keys()])


"""读队列，读线程把帧送到队列，写线程写回mp4文件"""
reading_queue = Queue()

"""摄像头类，每个摄像头地址对应一个摄像头，管理着该摄像头对应的管道，方法包含读、写操作"""


class Camera:
    def __init__(self, name, url, duration):
        conn = psycopg2.connect("dbname='vision' user='postgres' host='10.106.128.94' password='123456'")
        cur = conn.cursor()
        self.name = name
        self.url = url
        self.sample_rate = 25
        self.duration_in_sec = duration
        self._stop_event = Event()
        self.models = {}
        cur.execute(
            """SELECT * from camera.model WHERE camera_id IN (SELECT id from camera.camera WHERE name = '{}' )""".format(
                self.name))
        model_list = cur.fetchall()
        """模型及部分参数初始化"""
        for model in model_list:
            if int(model[3]) < self.sample_rate:
                self.sample_rate = int(model[3])
            # print("sample rate:"+model[3])
            self.camera_id = int(model[1])
            config = model[4]
            config['address'] = (config['host'], config['port'])
            if model[2] == 'pedestrian_structral':
                self.models['PedestrianStructural'] = PedestrianStructural(mode="client", **config)
            elif model[2] == 'object_detection':
                self.models['ObjectDetection'] = ObjectDetection(mode="client", **config)
            elif model[2] == 'vehicle_sturctral':
                self.models['VehicleStructural'] = VehicleStructural(mode="client", **config)
            elif model[2] == 'license_detection':
                self.models['LicenseDetection'] = LicenseDetection(mode="client", **config)
            elif model[2] == 'face_feature':
                self.models['FaceFeature'] = FaceFeature(mode="client", **config)
            elif model[2] == 'face_compare':
                self.models['FaceCompare'] = FaceCompare(mode="client", **config)
            # elif model[2] == 'gender_structral':
            #    self.models['GenderStructural'] = GenderStructural(mode="client", **config)
            # elif model[2] == 'age_structral':
            #    self.models['AgeStructural'] = AgeStructural(mode="client", **config)
        conn.close()

    """打开直播管道"""

    def open_pipe(self):
        """不做可视化渲染就没必要开stdin管道写入了（上面的写法），直接开一个子程序转推原始流即可，省时省开销"""
        self.pipe = subprocess.Popen([FFMPEG_BIN,
                                      '-y',  # (optional) overwrite output file if it exists
                                      '-loglevel', 'error',
                                      '-rtsp_transport', 'tcp',
                                      '-i', self.url,  # The input comes from a pipe
                                      '-codec:v', 'copy',
                                      '-an',  # Tells FFMPEG not to expect any audio
                                      '-q', '15',
                                      '-f', 'flv',
                                      f'rtmp://0.0.0.0:1935/live/{self.name}']
                                     )

    def init(self):
        """摄像头解码初始化及摄像头信息的获取"""
        camera_init_mutex.acquire()
        self.open_pipe()
        print("open camera:" + self.url)
        self.video_capture = cv2.VideoCapture(f'rtmp://127.0.0.1:1935/live/{self.name}')
        self.fps = self.video_capture.get(cv2.CAP_PROP_FPS)
        self.framesize = '%dx%d' % (
            self.video_capture.get(cv2.CAP_PROP_FRAME_WIDTH), self.video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        # print("fps:" + str(self.fps))
        # print("framesize:" + self.framesize)
        # print("duration:" + str(self.duration_in_sec))
        self.mp4 = None
        self.mp4_file = None
        self.video_id = None
        self.index = 0
        camera_init_mutex.release()

    def read(self):
        """循环读摄像头，由读线程实现"""
        self.init()
        while self.video_capture.isOpened() and not self._stop_event.is_set():
            ret, frame = self.video_capture.read()
            if ret:
                reading_queue.put(Frame(self, self.index, frame, datetime.datetime.now()))
                self.index += 1
            else:
                pass
        self.close()

    @staticmethod
    def make_dirs(path):
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def open_mp4(self, name, start, duration):
        """打开mp4管道及文件"""
        if self.mp4 != None:
            self.mp4.stdin.close()
        path = 'outputvideos/mp4/%s/%s' % (self.name, name)
        self.make_dirs(path)
        self.mp4_file = name
        conn = psycopg2.connect("dbname='vision' user='postgres' host='10.106.128.94' password='123456'")
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO camera.video(camera_id,path,start_date,duration) VALUES(%s,%s,%s,%s) RETURNING id """,
            (self.camera_id, path, start, duration))
        self.video_id = int(cur.fetchone()[0])
        conn.commit()
        conn.close()
        self.mp4 = subprocess.Popen([FFMPEG_BIN,
                                     '-y',  # (optional) overwrite output file if it exists
                                     '-f', 'rawvideo',
                                     # '-loglevel','error',
                                     '-s', self.framesize,  # '420x360', # size of one frame
                                     '-pix_fmt', 'bgr24',
                                     '-r', str(self.fps),  # frames per second
                                     '-i', '-',  # The input comes from a pipe
                                     '-an',  # Tells FFMPEG not to expect any audio
                                     '-vcodec', 'h264_nvenc',
                                     '-gpu', '1',
                                     path]
                                    , stdin=subprocess.PIPE)

    def write_mp4(self, f):
        """实际的管道写入，同时管理mp4管道，到时间点则更新管道（开启下一个文件）"""

        t = f.timestamp
        t = datetime.datetime(t.year, t.month, t.day, t.hour, t.minute - t.minute % (int(self.duration_in_sec / 60)))
        name = '%d%02d%02d/%d%02d%02d%02d%02d.mp4' % (t.year, t.month, t.day, t.year, t.month, t.day, t.hour, t.minute)
        if not self._stop_event.is_set():
            if not self.mp4:
                self.open_mp4(name, f.timestamp, self.duration_in_sec - (f.timestamp - t).total_seconds())
            elif self.mp4_file != name:
                self.open_mp4(name, t, self.duration_in_sec)
            try:
                self.mp4.stdin.write(f.frame)
            except ValueError:
                print('leak!!')

    def write(self, frame):
        """写帧操作，并对帧进行分析，由写线程实现"""

        if not self._stop_event.is_set():
            self.write_mp4(frame)

        if frame.index % self.sample_rate == 0:

            conn = psycopg2.connect("dbname='vision' user='postgres' host='10.106.128.94' password='123456'")
            cur = conn.cursor()

            t = frame.timestamp
            path = 'result/%s/%d%02d%02d/%02d%02d%02d%06d.jpg' % (
                self.name, t.year, t.month, t.day, t.hour, t.minute, t.second, t.microsecond)
            self.make_dirs(path)
            cv2.imwrite(path, frame.frame)
            cur.execute("""INSERT INTO camera.frame(video_id,path,create_date) VALUES(%s,%s,%s) RETURNING id""",
                        (frame.camera.video_id, path, frame.timestamp))
            frame_id = int(cur.fetchone()[0])

            img = Image.fromarray(cv2.cvtColor(frame.frame, cv2.COLOR_BGR2RGB))
            if 'ObjectDetection' in self.models:
                for obj in frame.camera.models['ObjectDetection'].analysis(img):
                    if 'PedestrianStructural' in frame.camera.models:
                        if obj[0] == "person":
                            x, y, w, h = obj[2]
                            box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                            cur.execute(
                                """INSERT INTO camera.object (frame_id, x, y, w, h, obj_type)
                                    VALUES (%s, %s, %s, %s, %s, 'person') RETURNING id""",
                                (frame_id, int(x - w / 2), int(y - h / 2), int(w), int(h)))
                            object_id = int(cur.fetchone()[0])
                            res: dict = frame.camera.models['PedestrianStructural'].analysis(
                                img.crop(tuple(map(int, box))))
                            cur.execute("""INSERT INTO camera.person(object_id,features) VALUES(%s,%s)""",
                                        (object_id, ' '.join(res.keys())))
                    if 'VehicleStructural' in frame.camera.models:
                        if obj[0] in ("car", "bus", "truck"):
                            x, y, w, h = obj[2]
                            box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                            cur.execute(
                                """INSERT INTO camera.object (frame_id, x, y, w, h, obj_type)
                                    VALUES (%s, %s, %s, %s, %s, 'car') RETURNING id""",
                                (frame_id, int(x - w / 2), int(y - h / 2), int(w), int(h)))
                            object_id = int(cur.fetchone()[0])

                            res = frame.camera.models['LicenseDetection'].analysis(img.crop(tuple(map(int, box))))
                            cur.execute("""INSERT INTO camera.car(object_id,license,type) VALUES(%s,%s,%s)""",
                                        (object_id, res['license'], obj[0]))
            conn.commit()
            conn.close()

    def close(self):
        self.pipe.stdin.close()
        self.mp4.stdin.close()


class Frame:
    """帧类，包括具体的帧数据及所属摄像头对象，通过调用摄像头的写方法实现写操作"""

    def __init__(self, camera, index, frame, timestamp):
        self.camera = camera
        self.index = index
        self.frame = frame
        self.timestamp = timestamp


class PerfThread(Thread):
    """线程基类"""

    def __init__(self):
        Thread.__init__(self)
        self.perf = PerfLogger()


class ReadThread(PerfThread):
    """读线程"""

    def __init__(self, camera):
        PerfThread.__init__(self)
        self.camera = camera
        self._stop_event = Event()

    def run(self):
        self.camera.read()

    def stop(self):
        self._stop_event.set()
        self.camera._stop_event.set()


class WriteThread(PerfThread):
    """写线程"""

    def __init__(self):
        PerfThread.__init__(self)
        self._stop_event = Event()

    def run(self):
        while not self._stop_event.is_set():
            f = reading_queue.get()
            self.perf.enter('write')
            f.camera.write(f)
            self.perf.exit('write')

    def stop(self):
        self._stop_event.set()


class demo_app(Thread):
    """摄像头管理类，线程，读取数据库信息并启动我们的分析程序，同时提供方法在摄像头列表变化时进行相应的响应"""

    def __init__(self):
        super(demo_app, self).__init__()
        self.add_camera_list = []
        self.delete_camera_list = []
        self.camera_list = []

    def run(self):
        conn = psycopg2.connect("dbname='vision' user='postgres' host='10.106.128.94' password='123456'")
        cur = conn.cursor()
        cur.execute("""SELECT * from camera.camera""")
        self.camera_list = cur.fetchall()
        """一个摄像头：一个读线程/2个写线程，能保证没有时延"""
        self.reading_threads = [ReadThread(Camera(x[1], x[2], x[8])) for x in self.camera_list]
        self.writing_threads = [WriteThread() for x in range(len(self.camera_list) * 2)]

        for t in self.reading_threads:
            t.start()
        for t in self.writing_threads:
            t.start()
        conn.close()
        """持续运行，当检测到摄像头列表变化时进行进行相应操作"""
        while True:
            # print(self.add_camera_list)
            if len(self.delete_camera_list) > 0:
                for i in range(len(self.delete_camera_list) * 2):
                    self.writing_threads[i].stop()
                names = [x[1] for x in self.delete_camera_list]
                for t in self.reading_threads:
                    if t.camera.name in names:
                        t.stop()
                del self.delete_camera_list[:]
                self.reading_threads = [x for x in self.reading_threads if not x._stop_event.is_set()]
                self.writing_threads = [x for x in self.writing_threads if not x._stop_event.is_set()]
            if len(self.add_camera_list) > 0:
                extend_reading_threads = [ReadThread(Camera(x[1], x[2], x[8])) for x in self.add_camera_list]
                extend_writing_threads = [WriteThread() for x in range(len(self.add_camera_list) * 2)]
                for t in extend_reading_threads:
                    t.start()
                for t in extend_writing_threads:
                    t.start()
                del self.add_camera_list[:]
                self.reading_threads.extend(extend_reading_threads)
                self.writing_threads.extend(extend_writing_threads)

            time.sleep(1)

        print('exiting')
        exiting.set()

    """刷新方法，查数据库以获取更新后的列表"""

    def refresh(self):
        conn = psycopg2.connect("dbname='vision' user='postgres' host='10.106.128.94' password='123456'")
        cur = conn.cursor()
        cur.execute("""SELECT * from camera.camera""")
        new_camera_list = cur.fetchall()
        self.add_camera_list = list(set(new_camera_list).difference(set(self.camera_list)))
        self.delete_camera_list = list(set(self.camera_list).difference(set(new_camera_list)))
        self.camera_list = new_camera_list
        conn.close()
