# People Counting on Bus Project Using OpenCV

![Screenshot 2025-06-03 224544](https://github.com/user-attachments/assets/88b3d584-6434-482d-9aff-821df8464911)


## Overview
This project implements a people counting system for buses using a Raspberry Pi Zero 2W as the edge computing device. It employs background subtraction with OpenCV’s MOG2 algorithm for person detection, a 5MP Pi Camera for capturing video frames, and MQTT to send processed data to a ThingsBoard dashboard for real-time monitoring. The system tracks people entering and exiting the bus, calculates the number of people inside, and monitors system resources (CPU, memory, and temperature). It is optimized for the resource-constrained Raspberry Pi Zero 2W, using threaded frame reading and low-resolution processing.

## Repository Contents
- **counter.py**: Main script for processing video from the Pi Camera or a video file. It performs person detection using background subtraction, tracking, counting, and sends telemetry data to ThingsBoard.
- **postTelemetry_mqtt_tb.py**: Utility script for handling MQTT communication with the ThingsBoard server to send telemetry data.
- **Person.py**: Defines the `MyPerson` and `MultiPerson` classes for tracking individual and multiple persons based on centroids and movement direction.

## Features
- **Person Detection**: Uses OpenCV’s MOG2 background subtraction for lightweight person detection, suitable for the Raspberry Pi Zero 2W.
- **Tracking**: Tracks persons using centroid-based tracking with the `MyPerson` class, assigning unique IDs and monitoring movement across defined lines.
- **Counting Logic**: Counts people crossing two virtual lines (upper for “Out” and lower for “In”) to determine entries and exits from the bus.
- **Telemetry**: Sends real-time data (entry/exit counts, people inside, CPU usage, memory usage, temperature, and FPS) to a ThingsBoard dashboard.
- **Resource Monitoring**: Tracks CPU, memory, and temperature usage on the Raspberry Pi Zero 2W for performance optimization.
- **Threaded Frame Reading**: Uses custom `PiCameraReader` and `VideoReader` classes for efficient frame capture from the Pi Camera or video files.
- **Frame Optimization**: Processes frames at a low resolution (320x240 for Pi Camera) to optimize performance on the Raspberry Pi Zero 2W.

## Hardware Requirements
- **Raspberry Pi Zero 2W**: Acts as the edge computing device.
- **Pi Camera Module (5MP)**: Captures video frames for person detection.
- **Internet Connection**: Required for sending telemetry data to ThingsBoard.

## Software Requirements
- **Python 3.7+**
- **OpenCV**: For computer vision tasks and background subtraction.
  ```bash
  pip install opencv-python
  ```
- **Picamera2**: For interfacing with the Pi Camera.
  ```bash
  pip install picamera2
  ```
- **Paho MQTT**: For communication with ThingsBoard.
  ```bash
  pip install paho-mqtt
  ```
- **Psutil**: For resource monitoring.
  ```bash
  pip install psutil
  ```
- **Imutils**: For image processing utilities.
  ```bash
  pip install imutils
  ```

## Setup Instructions
1. **Install Dependencies**:
   Ensure all required Python packages are installed using the commands above.
2. **Configure ThingsBoard**:
   - Set up a ThingsBoard server (e.g., `app.coreiot.io` or a local instance).
   - Create a device in ThingsBoard and obtain the **device access token**.
   - Note the server IP and MQTT port (e.g., 1883).
3. **Connect Pi Camera**:
   - Ensure the 5MP Pi Camera is properly connected to the Raspberry Pi Zero 2W.
   - Enable the camera interface in `raspi-config`.
4. **Run the Script**:
   - For Pi Camera operation:
     ```bash
     python3 counter.py --server-IP <THINGSBOARD_IP> --Port <MQTT_PORT> --token <DEVICE_TOKEN>
     ```
   - For testing with a video file:
     ```bash
     python3 counter.py --input <VIDEO_FILE_PATH> --server-IP <THINGSBOARD_IP> --Port <MQTT_PORT> --token <DEVICE_TOKEN>
     ```
5. **View Dashboard**:
   - Access the ThingsBoard dashboard to monitor:
     - Number of people entering (`entered_people`)
     - Number of people exiting (`exited_people`)
     - Current people inside (`people_inside`)
     - System metrics (CPU usage, memory usage, temperature, FPS)

## Usage Notes
- **Single Camera**: Optimized for the Raspberry Pi Zero 2W with low-resolution processing (320x240) and threaded frame reading.
- **Counting Logic**: Two horizontal lines are drawn in the frame (upper at 1/6 height for “Out,” lower at 4/6 height for “In”). People crossing these lines are counted based on their direction.
- **Performance**: Background subtraction is lightweight but sensitive to lighting changes. Adjust `areaTH` in `counter.py` if detection is too sensitive or misses objects.
- **Exit**: Press `Esc` to quit or use `Ctrl+C` to gracefully exit, displaying average resource usage and FPS.
- **Threading**: The `PiCameraReader` and `VideoReader` classes use threading to prevent frame reading from blocking the main processing loop.
- **Video Input**: For video files, the script adjusts line positions dynamically based on frame size and crops 20 pixels from the left to improve processing.

## Dashboard Example
 ![Screenshot 2025-06-03 211056](https://github.com/user-attachments/assets/cbb0fb58-f331-4a4d-9ebc-9c0204fe77c5)
 ![Screenshot 2025-06-03 211103](https://github.com/user-attachments/assets/ce96f62d-67c0-4cc1-a9c0-4bd79099c53a)

 - You can view the example dashboard via this link: [My Dashboard](https://app.coreiot.io/dashboard/5eef5c50-3ca9-11f0-aae0-0f85903b3644?publicId=00e331c0-f1ec-11ef-87b5-21bccf7d29d5).
 - if you want to manipulate with [My Dashboard](https://app.coreiot.io/dashboard/5eef5c50-3ca9-11f0-aae0-0f85903b3644?publicId=00e331c0-f1ec-11ef-87b5-21bccf7d29d5), you can run this command:
   
 ```bash
  python counter.py -i test1.mp4 --server-IP app.coreiot.io -P 1883 -a I1WYm7V1FMBsKgBLMJVL
 ```

 (For testing with test1.mp4).

## Limitations
- **Single Camera**: Assumes a single entry/exit point. Multiple entry points may require additional cameras or logic.
- **Background Subtraction**: Sensitive to lighting changes and shadows, which may cause false detections. Use in controlled lighting conditions or adjust MOG2 parameters.
- **Raspberry Pi Zero 2W**: Limited processing power may lead to lower FPS. Tune resolution or frame processing frequency for performance.
- **No Data Logging**: Unlike other implementations, this script does not log counts to a file. Add CSV logging if needed.
- **Unused Code**: Some commented-out code (e.g., `MultiPerson` usage, trajectory drawing) suggests incomplete features that could be implemented for enhanced tracking.

## Future Improvements
- Implement CSV logging for entry/exit events with timestamps.
- Enhance background subtraction with adaptive thresholding or shadow removal for better accuracy.
- Add support for multiple entry/exit points with additional cameras.
- Integrate `MultiPerson` class for handling groups of people.
- Optimize MOG2 parameters for bus-specific lighting conditions.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact
For questions or contributions, please contact [thinhle.hardware@gmail.com](mailto:thinhle.hardware@gmail.com) or
[My Linkedin](https://www.linkedin.com/in/lelocquocthinh/) or open an issue on the repository.

*LeLocQuocThinh/ 06-2025 - © <a href="https://github.com/LELOCQUOCTHINH" target="_blank">LLQT</a>.*
