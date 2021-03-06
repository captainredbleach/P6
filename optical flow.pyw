import multiprocessing
from threading import Thread
import numpy as np
import cv2
import os
import time
from multiprocessing.pool import ThreadPool
from collections import deque
import queue

my_queue = queue.Queue()

def storeInQueue(f):
    def wrapper(*args):
        my_queue.put(f(*args))
    return wrapper
    
@storeInQueue
def draw_flow(img, flow, hsv, step=24):
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
    hsv[..., 0] = ang*180/np.pi/2
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    h, w = img.shape[:2]
    y, x = np.mgrid[step/2:h:step, step/2:w:step].reshape(2,-1).astype(int)    
    fx, fy = flow[y,x].T

    lines = np.vstack([x, y, x-fx, y-fy]).T.reshape(-1, 2, 2)
    lines = np.int32(lines + 0.5)
    cv2.polylines(img, lines, 0, (0, 255, 0))

    for (x1, y1), (_x2, _y2) in lines:
        cv2.circle(img, (x1, y1), 1, (0, 255, 0), -1)
    
    direction = [fx[x] for x in np.arange(len(lines)) if np.abs(fx[x]) > 20]
    
    if len(direction)>=1:
        d = np.sum(direction) // len(direction)
        print(d)
    
    
    return img, bgr

def calc(prevgray, gray, hsv, img):
    flow = cv2.calcOpticalFlowFarneback(prevgray, gray, None, 0.3, 10, 25, 2, 15, 1.7, 0)
    t1 = Thread(target=draw_flow, args=(img, flow, hsv))
    t1.start()
    t1.join()
    res, br = my_queue.get()
    
    return res, br

thread_num = multiprocessing.cpu_count()
pool = ThreadPool(processes=thread_num)
pending_task = deque()


video_name = "15FPS_720PL.mp4"
path = os.path.dirname(os.path.realpath(__file__))
cap = cv2.VideoCapture(os.path.join(path, video_name))

suc, prev = cap.read()
prevgray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
hsv = np.zeros_like(prev)
hsv[..., 1] = 255

while True:
    while len(pending_task) > 0 and pending_task[0].ready():
            #print(len(pending_task))
            f, h = pending_task.popleft().get()
            cv2.imshow('flow', f)
            cv2.imshow('flow HSV', h)
            
    if len(pending_task) < thread_num:
        suc, img = cap.read()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        task = pool.apply_async(calc, (prevgray, gray, hsv, img))
        pending_task.append(task)

        prevgray = gray
    time.sleep(1 / 15)
    if cv2.waitKey(1) & 0xFF == ord('q'):
                break


cap.release()
cv2.destroyAllWindows()