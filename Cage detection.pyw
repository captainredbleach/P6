from threading import Thread
import numpy as np
import cv2
import os
import time
from multiprocessing.pool import ThreadPool
from multiprocessing.pool import ThreadPool
from multiprocessing import current_process
from collections import deque

def filtering(frame):
    frame = cv2.bilateralFilter(frame, 5, 75, 75)
    
    frame = cv2.medianBlur(frame, 15)
    
    frame = cv2.GaussianBlur(frame,(15,15), cv2.BORDER_DEFAULT)
    
    return frame

def flood(img_final):
    im_floodfill = img_final.copy()
    # Mask used to flood filling.
    # Notice the size needs to be 2 pixels than the image.
    h, w = img_final.shape[:2]
    maskf = np.zeros((h+2, w+2), np.uint8)

    # Floodfill from point (0, 0)
    cv2.floodFill(im_floodfill, maskf, (0,0), 255);

    # Invert floodfilled image
    im_floodfill_inv = cv2.bitwise_not(im_floodfill)

    # Combine the two images to get the foreground.
    
    return img_final | im_floodfill_inv 

def process(rgb, hsv, frame):
    
    edge = cv2.Canny(frame, 140, 160, apertureSize=3, L2gradient = True)
    
    frame = filtering(frame)

    lower_g = np.array([30, 15, 15])
    upper_g = np.array([90, 40, 240])
 
    # preparing the mask to overlay
    mask_g = cv2.inRange(hsv, lower_g, upper_g)
    
    mask_E = cv2.bitwise_and(mask_g, edge)

    # The black region in the mask has the value of 0,
    # so when multiplied with original image removes all non-grey regions
    result_g = cv2.bitwise_and(frame, frame, mask = mask_E)
    
    result_g = np.abs(result_g) * 4
    
    kernel = np.ones((5,5), np.uint8)
    thresh = cv2.threshold(result_g, 5, 255, cv2.THRESH_BINARY)[1]
    img_dilation = cv2.dilate(thresh, kernel, iterations=50)
    img_erosion = cv2.erode(img_dilation, kernel, iterations=65)
    
    img_erosion2 = cv2.erode(img_erosion, kernel, iterations=2)
    img_dilation2 = cv2.dilate(img_erosion2, kernel, iterations=30)
    
    finalE = cv2.erode(img_dilation2, kernel, iterations=4)
    img_final = np.abs(img_dilation2) - np.abs(finalE)
    
    
    im_out = flood(img_final)
    
    cnts = cv2.findContours(im_out, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]
    for c in cnts:
        rect = cv2.minAreaRect(c)
        width = rect[1][0]
        height = rect[1][1]
        if (width < 400) and (height < 800) and (width >= 150) and (height > 200) and ((width * 1.15 < height) or (height * 1.15 < width)):
            c = max(cnts, key = cv2.contourArea)
            x,y,w,h = cv2.boundingRect(c)
            cv2.rectangle(rgb, (x, y), (x + w, y + h), (0,0,255), 2)
            tC = hsv[y:y + h, x:x + w]
            lower_b = np.array([15, 100, 20])
            upper_b = np.array([20, 255, 200])
            mask_b = cv2.inRange(tC, lower_b, upper_b)
            result_b = cv2.bitwise_and(tC, tC, mask = mask_b)
            result_b = cv2.cvtColor(result_b, cv2.COLOR_HSV2BGR)
            result_b = cv2.cvtColor(result_b, cv2.COLOR_BGR2GRAY)
            thresh_b = cv2.threshold(result_b, 20, 255, cv2.THRESH_BINARY)[1]
            erosion_b = cv2.erode(thresh_b, kernel, iterations=1)
            dilation_b = cv2.dilate(erosion_b, kernel, iterations=10)
            finalB = cv2.erode(dilation_b, kernel, iterations=2)
            img_finalb = np.abs(dilation_b) - np.abs(finalB)
            b_out = flood(img_finalb)
            bcnts = cv2.findContours(b_out, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if bcnts[1] is not None:
                print("Cage with box")
                bcnts = bcnts[0] if len(bcnts) == 2 else bcnts[1]
                for bc in bcnts:
                    bc = max(bcnts, key = cv2.contourArea)
                    bx,by,bw,bh = cv2.boundingRect(bc)
                    cv2.rectangle(rgb[y:y + h, x:x + w], (bx, by), (bx + bw, by + bh), (0,0,255), 2)
            else:
                pass
            
    #print(current_process().name)
    return rgb, mask_E

def frameIO():
    thread_num = cv2.getNumberOfCPUs() - 1
    pool = ThreadPool(processes=thread_num)
    pending_task = deque()
    
    video_name = "30FPS_720P.mp4"
    path = os.path.dirname(os.path.realpath(__file__))
    cap = cv2.VideoCapture(os.path.join(path, video_name))
    fps = np.rint(cap.get(cv2.CAP_PROP_FPS)) * thread_num
    prev_frame = None 
    
    while cap.isOpened():
        while len(pending_task) > 0 and pending_task[0].ready():
            #print(len(pending_task))
            res, debug = pending_task.popleft().get()
            cv2.imshow('result', res)
            if debug is not None:
                cv2.imshow('debug', debug)    
                
        if len(pending_task) < thread_num:
            ret, cur_frame = cap.read()
            
            if ret:
                cur_frame = cv2.resize(cur_frame, (1280, 720))
                
        
                if prev_frame is not None:
                    # It converts the BGR color space of image to HSV color space
                    hsv = cv2.cvtColor(cur_frame, cv2.COLOR_BGR2HSV)
                    prev_frame = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                    diff_frame = cv2.cvtColor(cur_frame, cv2.COLOR_BGR2GRAY)
                    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(6,11))
                    prev_frame = clahe.apply(prev_frame)
                    diff_frame = clahe.apply(diff_frame)
                    cv2.normalize(diff_frame, diff_frame, 0, 255, cv2.NORM_MINMAX)
                    cv2.normalize(prev_frame, prev_frame, 0, 255, cv2.NORM_MINMAX)
                    diff = cv2.absdiff(prev_frame, diff_frame, 0.5)
                    #diff = diff * 2
                    #process(cur_frame, hsv, diff)
                    task = pool.apply_async(process, (cur_frame, hsv, diff))
                    pending_task.append(task)
                    
            else:
                break
            
        if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        time.sleep(1 / fps)
        prev_frame = cur_frame.copy()
    cv2.destroyAllWindows()
    cap.release()

def main():
    p1 = Thread(target=frameIO) 
    p1.start()
    p1.join()
    #RFID her

if __name__ == '__main__':
    main()