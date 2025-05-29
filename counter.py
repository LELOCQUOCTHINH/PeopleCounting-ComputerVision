##People counter
import numpy as np
import cv2
import Person
import time
import requests
import imutils
import signal
import sys
import threading
import queue
import logging
import argparse
from picamera2 import Picamera2
import psutil

# setup logger
logging.basicConfig(level=logging.DEBUG, format="[DEBUG] %(message)s")
logger = logging.getLogger(__name__)

# Signal handler for Ctrl+C (negligible resource use, safe for Pi Zero 2 W)
def signal_handler(sig, frame):
    print("Ctrl+C detected, cleaning up...")
    global running
    running = False
    if isinstance(source, PiCameraReader):
        source.release()
    else:
        source.release()
    cv2.destroyAllWindows()
    # Print average resource usage
    if cpu_usages:
        print(f"Average CPU Usage: {sum(cpu_usages)/len(cpu_usages):.2f}%")
    if memory_usages:
        print(f"Average Memory Usage: {sum(memory_usages)/len(memory_usages):.2f}%")
    if temperatures:
        print(f"Average Temperature: {sum(temperatures)/len(temperatures):.2f}°C")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

class VideoReader:
    def __init__(self, source):
        logger.debug(f"Initializing VideoReader with source: {source}")
        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            logger.error(f"Failed to open video source: {source}")
            raise ValueError(f"Failed to open video source: {source}")
        logger.debug(f"Video FPS: {self.cap.get(cv2.CAP_PROP_FPS)}")
        logger.debug(f"Video frame count: {self.cap.get(cv2.CAP_PROP_FRAME_COUNT)}")
        self.q = queue.Queue(maxsize=10)
        self.running = True
        self.frame_count = 0
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._reader)
        self.thread.daemon = True
        self.thread.start()
        time.sleep(0.5)

    def _reader(self):
        retry_count = 0
        max_retries = 5
        while self.running and retry_count < max_retries:
            with self.condition:
                while self.q.full() and self.running:
                    #logger.debug("Queue full, read-thread waiting")
                    self.condition.wait()
                if not self.running:
                    break
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    retry_count += 1
                    logger.warning(f"Failed to read frame (attempt {retry_count}/{max_retries})")
                    time.sleep(0.5)
                    continue
                self.q.put(frame)
                self.frame_count += 1
                #logger.debug(f"Frame read, frame {self.frame_count}, queue size: {self.q.qsize()}")
                retry_count = 0
                time.sleep(0.005)
        if retry_count >= max_retries:
            #logger.error("Max retries reached, stopping reader thread")
            self.running = False

    def read(self):
        with self.condition:
            frame = None
            try:
                frame = self.q.get_nowait()
                self.condition.notify()
            except queue.Empty:
                pass
            return frame

    def release(self):
        self.running = False
        with self.condition:
            self.condition.notify()
        self.cap.release()
        logger.debug("VideoCapture released")

class PiCameraReader:
    def __init__(self):
        logger.debug("Initializing PiCameraReader")
        self.camera = Picamera2()
        config_cam = self.camera.create_video_configuration(main={"size": (320, 240), "format": "RGB888"})
        self.camera.configure(config_cam)
        self.camera.start()
        self.q = queue.Queue(maxsize=10)
        self.running = True
        self.frame_count = 0
        self.condition = threading.Condition()
        self.thread = threading.Thread(target=self._reader)
        self.thread.daemon = True
        self.thread.start()
        time.sleep(0.5)

    def _reader(self):
        while self.running:
            with self.condition:
                while self.q.full() and self.running:
                    #logger.debug("Queue full, read-thread waiting")
                    self.condition.wait()
                if not self.running:
                    break
                frame = self.camera.capture_array()
                if frame is not None:
                    self.q.put(frame)
                    self.frame_count += 1
                    #logger.debug(f"Frame read, frame {self.frame_count}, queue size: {self.q.qsize()}")
                time.sleep(0.005)

    def read(self):
        with self.condition:
            frame = None
            try:
                frame = self.q.get_nowait()
                self.condition.notify()
            except queue.Empty:
                pass
            return frame

    def release(self):
        self.running = False
        with self.condition:
            self.condition.notify()
        self.camera.stop()
        logger.debug("PiCamera released")

def process_frames(source, process_q, display_q):
    #Background Substractor
    fgbg = cv2.createBackgroundSubtractorMOG2(detectShadows=True)

    #Structuring elements for morphographic filters
    kernelOp = np.ones((3,3),np.uint8)
    kernelOp2 = np.ones((5,5),np.uint8)
    kernelCl = np.ones((11,11),np.uint8)

    #Variables
    font = cv2.FONT_HERSHEY_SIMPLEX
    persons = []
    max_p_age = 1
    pid = 1
    back = None
    cnt_up = 0
    cnt_down = 0

    #Lines coordinate for counting
    h, w = 240, 320  # Default for PiCamera, updated for video
    frameArea = h * w
    areaTH = frameArea / 300
    line_up = int(1 * (h / 6))
    line_down = int(4 * (h / 6))
    up_limit = int(0.5 * (h / 6))
    down_limit = int(4.5 * (h / 6))
    line_down_color = (255,0,0)
    line_up_color = (0,0,255)
    pt1 = [0, line_down]
    pt2 = [w, line_down]
    pts_L1 = np.array([pt1,pt2], np.int32).reshape((-1,1,2))
    pt3 = [0, line_up]
    pt4 = [w, line_up]
    pts_L2 = np.array([pt3,pt4], np.int32).reshape((-1,1,2))
    pt5 = [0, up_limit]
    pt6 = [w, up_limit]
    pts_L3 = np.array([pt5,pt6], np.int32).reshape((-1,1,2))
    pt7 = [0, down_limit]
    pt8 = [w, down_limit]
    pts_L4 = np.array([pt7,pt8], np.int32).reshape((-1,1,2))

    while running:
        frame = source.read()
        if frame is None:
            if source.q.qsize() == 0:
                logger.debug("No more frames, stopping process thread")
                display_q.put((None, cnt_up, cnt_down))
                break
            continue

        # Update dimensions for video files
        if isinstance(source, VideoReader):
            h, w = frame.shape[:2]
            frameArea = h * w
            areaTH = frameArea / 300
            line_up = int(1 * (h / 6))
            line_down = int(4 * (h / 6))
            up_limit = int(0.5 * (h / 6))
            down_limit = int(4.5 * (h / 6))
            pt1 = [0, line_down]
            pt2 = [w, line_down]
            pts_L1 = np.array([pt1,pt2], np.int32).reshape((-1,1,2))
            pt3 = [0, line_up]
            pt4 = [w, line_up]
            pts_L2 = np.array([pt3,pt4], np.int32).reshape((-1,1,2))
            pt5 = [0, up_limit]
            pt6 = [w, up_limit]
            pts_L3 = np.array([pt5,pt6], np.int32).reshape((-1,1,2))
            pt7 = [0, down_limit]
            pt8 = [w, down_limit]
            pts_L4 = np.array([pt7,pt8], np.int32).reshape((-1,1,2))
            frame = frame[:,20:]

        #Apply background subtraction
        fgmask = fgbg.apply(frame)
        fgmask2 = fgbg.apply(frame)

        #Binarization to eliminate shadows
        try:
            ret, imBin = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)
            ret, imBin2 = cv2.threshold(fgmask2, 200, 255, cv2.THRESH_BINARY)
            #Opening (erode->dilate) to remove noise.
            mask = cv2.morphologyEx(imBin, cv2.MORPH_OPEN, kernelOp)
            mask2 = cv2.morphologyEx(imBin2, cv2.MORPH_OPEN, kernelOp)
            #Closing (dilate -> erode) to join white regions.
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernelCl)
            mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernelCl)
            if back is None:
                back = mask
                continue
            mask = cv2.absdiff(back, mask)
        except:
            logger.debug("Processing error, stopping process thread")
            display_q.put((None, cnt_up, cnt_down))
            break

        #################
        #   CONTOURS   #
        #################
        
        # RETR_EXTERNAL returns only extreme outer flags. All child contours are left behind.
        contours0, hierarchy = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours0:
            rect = cv2.boundingRect(cnt)
            
            area = cv2.contourArea(cnt)
            if area > areaTH:
                #################
                #   TRACKING    #
                #################
                
                #Missing conditions for multipersons, outputs and screen entries
                M = cv2.moments(cnt)
                cx = int(M['m10']/M['m00'])
                cy = int(M['m01']/M['m00'])
                x,y,w,h = cv2.boundingRect(cnt)
                # print ('working')
                
                new = True
                if cy in range(up_limit, down_limit):
                    for i in persons:
                        if abs(cx-i.getX()) <= w and abs(cy-i.getY()) <= h:
                            # the object is close to one that has already been detected before
                            # print 'update'
                            new = False
                            i.updateCoords(cx,cy)   #update coordinates in the object and resets age
                            if i.going_UP(line_down,line_up) == True and i.getDir() == 'up':
                                # if w > 100:
                                #     count_up = w/60
                                #     #cnt_up += count_up
                                  
                                # else:    
                                #     cnt_up += 1
                                cnt_up += 1
                                #i.updateCoords(cx,cy)
                                print ("ID:",i.getId(),'crossed going out at',time.strftime("%c"))
                            elif i.going_DOWN(line_down,line_up) == True and i.getDir() == 'down':
                                # if w > 100:
                                #     count_down = w/60
                                #     #cnt_down += count_down
                                # else:
                                #     cnt_down += 1
                                #i.updateCoords(cx,cy)
                                cnt_down += 1
                                print ("ID:",i.getId(),'crossed going in at',time.strftime("%c"))
                            break
                        if i.getState() == '1':
                            if i.getDir() == 'down' and i.getY() > down_limit:
                                i.setDone()
                            elif i.getDir() == 'up' and i.getY() < up_limit:
                                i.setDone()
                        if i.timedOut():
                            #get out of the people list
                            index = persons.index(i)
                            persons.pop(index)
                            del i     #free the memory of i
                    if new == True:
                        p = Person.MyPerson(pid,cx,cy, max_p_age)
                        persons.append(p)
                        pid += 1    
              
                #################
                #   DRAWINGS     #
                #################
                cv2.circle(frame,(cx,cy), 5, (0,0,255), -1)
                img = cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),1)            
                #cv2.drawContours(frame, cnt, -1, (0,255,0), 3)
        
        #END for cnt in contours0
                
        #########################
        # DRAWING TRAJECTORIES  #
        #########################
        #for i in persons:
        ##        if len(i.getTracks()) >= 2:
        ##            pts = np.array(i.getTracks(), np.int32)
        ##            pts = pts.reshape((-1,1,2))
        ##            frame = cv2.polylines(frame,[pts],False,i.getRGB())
        ##        if i.getId() == 9:
        ##            print str(i.getX()), ',', str(i.getY())
            #cv2.putText(frame, str(i.getId()),(i.getX(),i.getY()),font,0.3,i.getRGB(),1,cv2.LINE_AA)
            
        #################
        # DISPLAY ON FRAME    #
        #################
        str_up = 'Out: '+ str(cnt_up)
        str_down = 'In: '+ str(cnt_down)
        frame = cv2.polylines(frame,[pts_L1],False,line_down_color,thickness=2)
        frame = cv2.polylines(frame,[pts_L2],False,line_up_color,thickness=2)
        frame = cv2.polylines(frame,[pts_L3],False,(255,255,255),thickness=1)
        frame = cv2.polylines(frame,[pts_L4],False,(255,255,255),thickness=1)
        cv2.putText(frame, str_up ,(20,70),font,0.5,(255,255,255),2,cv2.LINE_AA)
        cv2.putText(frame, str_down ,(20,100),font,0.5,(255,255,255),2,cv2.LINE_AA)
        # out.write(frame)

        # Put processed frame in display queue
        display_q.put((frame, cnt_up, cnt_down))

def monitor_resources():
    global cpu_usages, memory_usages, temperatures
    last_time = time.time()
    while running:
        current_time = time.time()
        if current_time - last_time >= 10:
            cpu_usage = psutil.cpu_percent(interval=None)
            memory_usage = psutil.virtual_memory().percent
            try:
                with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                    temp = int(f.read()) / 1000.0
            except:
                temp = 0.0  # Fallback if temp not available
            cpu_usages.append(cpu_usage)
            memory_usages.append(memory_usage)
            temperatures.append(temp)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] CPU: {cpu_usage:.2f}%, Memory: {memory_usage:.2f}%, Temp: {temp:.2f}°C")
            last_time = current_time
        time.sleep(1)

def main():
    global running, source, cpu_usages, memory_usages, temperatures
    running = True
    cpu_usages = []
    memory_usages = []
    temperatures = []

    # Parse command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=str, default="picam",
                        help="Input source: video file path or 'picam' for PiCamera")
    args = parser.parse_args()

    # Initialize input source
    if args.input.lower() == "picam":
        logger.debug("Using PiCamera")
        source = PiCameraReader()
    else:
        logger.debug(f"Using video file: {args.input}")
        source = VideoReader(args.input)
        source.cap.set(3, 500) #Width
        source.cap.set(4, 500) #Height

    # Initialize queues
    process_q = queue.Queue(maxsize=10)
    display_q = queue.Queue(maxsize=10)

    # Start processing thread
    process_thread = threading.Thread(target=process_frames, args=(source, process_q, display_q))
    process_thread.daemon = True
    process_thread.start()

    # Start resource monitoring thread
    monitor_thread = threading.Thread(target=monitor_resources)
    monitor_thread.daemon = True
    monitor_thread.start()

    url = "http://10.10.7.148:8080/video"

    cnt_up = 0
    cnt_down = 0
    #count_up = 0    # Unused variable
    #count_down = 0  # Unused variable
    #state = 0       # Unused variable
    #rect_co = []  # Unused variable
    #val = []      # Unused variable

    # Main loop for display
    while running:
        try:
            frame_data = display_q.get_nowait()
            frame, cnt_up, cnt_down = frame_data
            if frame is None:
                print('EOF')
                print(('Out:'), cnt_up)
                print(('In:'), cnt_down)
                running = False
                # Print average resource usage
                if cpu_usages:
                    print(f"Average CPU Usage: {sum(cpu_usages)/len(cpu_usages):.2f}%")
                if memory_usages:
                    print(f"Average Memory Usage: {sum(memory_usages)/len(memory_usages):.2f}%")
                if temperatures:
                    print(f"Average Temperature: {sum(temperatures)/len(temperatures):.2f}°C")
                break
            cv2.imshow('Counting', frame)
            #cv2.imshow('track',mask)
            #cv2.imshow('Mask',mask)    
        except queue.Empty:
            pass

        #Press ESC to exit
        k = cv2.waitKey(30) & 0xff
        if k == 27:
            running = False
            # Print average resource usage
            if cpu_usages:
                print(f"Average CPU Usage: {sum(cpu_usages)/len(cpu_usages):.2f}%")
            if memory_usages:
                print(f"Average Memory Usage: {sum(memory_usages)/len(memory_usages):.2f}%")
            if temperatures:
                print(f"Average Temperature: {sum(temperatures)/len(temperatures):.2f}°C")
            break

    #Cleanup
    source.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()