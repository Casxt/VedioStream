#coding = utf - 8
from camera.demo_module import *

t = demo_app()
t.start()
'''
time.sleep(20)
conn = psycopg2.connect("dbname='camera_test' user='postgres' host='10.106.128.94' password='123456'")
cur = conn.cursor()
cur.execute("""INSERT INTO camera(name,url,face_detect,person_struct,car_struct) values('test','rtsp://192.168.3.58',True,True,True)""")
conn.commit()
t.refresh()
time.sleep(60)
cur.execute("""DELETE FROM camera WHERE name = 'test'""")
conn.commit()
t.refresh()
conn.close()
'''


