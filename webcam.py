# -*- coding: utf-8 -*-
"""
Gesture Control with Real-time Visualization Mask
"""
# 🔧 Очистка и установка библиотек
!pip uninstall -y tensorflow protobuf mediapipe -q
!pip install protobuf==4.25.3 mediapipe==0.10.14 paho-mqtt==1.6.1 opencv-python-headless -q

import cv2
import numpy as np
import mediapipe as mp
import random
import time
from paho.mqtt import client as mqtt_client
from IPython.display import display, Javascript
from google.colab.output import eval_js
from base64 import b64decode, b64encode

print("✅ Установка завершена.")

# ================= MQTT НАСТРОЙКИ =================
BROKER = 'broker.emqx.io'
PORT = 1883
TOPIC = 'ligarobotov/darkfaerie'  # 🔁 Измените на свой топик
CLIENT_ID = f'colab-gesture-{random.randint(0, 1000)}'

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT Broker!")
        else:
            print(f"❌ Failed to connect, return code {rc}")

    client = mqtt_client.Client(CLIENT_ID)
    client.on_connect = on_connect
    client.connect(BROKER, PORT)
    client.loop_start()
    return client

# ================= ВЕБ-КАМЕРА С ВИЗУАЛИЗАЦИЕЙ =================
def init_webcam():
    js = Javascript('''
    var video; var div = null; var stream;
    var maskElement; var labelElement; var pendingResolve = null; var shutdown = false;

    function removeDom() {
       if (stream) stream.getVideoTracks()[0].stop();
       if (video) video.remove(); if (div) div.remove();
       video = null; div = null; stream = null; maskElement = null; labelElement = null;
    }

    async function createDom() {
      if (div !== null) return stream;
      div = document.createElement('div');
      div.style.border = '2px solid black'; div.style.padding = '3px';
      div.style.width = '100%'; div.style.maxWidth = '600px';
      div.style.position = 'relative';
      document.body.appendChild(div);

      const statusOut = document.createElement('div');
      statusOut.innerHTML = "<span>Status: </span>";
      labelElement = document.createElement('span');
      labelElement.innerText = 'Initializing...';
      labelElement.style.fontWeight = 'bold';
      statusOut.appendChild(labelElement);
      div.appendChild(statusOut);

      video = document.createElement('video');
      video.style.display = 'block';
      video.style.width = '100%';
      video.setAttribute('playsinline', '');
      video.muted = true;
      video.autoplay = true;

      try {
          stream = await navigator.mediaDevices.getUserMedia({video: { facingMode: "user", width: 640, height: 480 }});
      } catch (e) {
          labelElement.innerText = "❌ CAMERA DENIED - Check browser permissions!";
          labelElement.style.color = "red";
          return null;
      }

      video.srcObject = stream;
      await video.play();
      div.appendChild(video);

      // 👇 Элемент маски для отрисовки скелета
      maskElement = document.createElement('img');
      maskElement.style.position = 'absolute';
      maskElement.style.top = '0';
      maskElement.style.left = '0';
      maskElement.style.width = '100%';
      maskElement.style.height = '100%';
      maskElement.style.pointerEvents = 'none';
      maskElement.style.zIndex = '10';
      maskElement.style.opacity = '0.85';
      div.appendChild(maskElement);

      const stopBtn = document.createElement('div');
      stopBtn.style.marginTop = '10px';
      stopBtn.innerHTML = '<span style="color: red; font-weight: bold; cursor: pointer; background: #eee; padding: 5px;">▶ Click here to STOP</span>';
      stopBtn.onclick = () => { shutdown = true; };
      div.appendChild(stopBtn);

      return stream;
    }

    async function stream_frame(label, maskBase64) {
      if (shutdown) { removeDom(); return ''; }

      let stream = await createDom();
      if (!stream) return '';

      labelElement.innerText = label;

      // 👇 Обновляем маску поверх видео
      if (maskBase64 && maskBase64 !== " ") {
        maskElement.src = maskBase64;
        maskElement.style.display = 'block';
      } else {
        maskElement.style.display = 'none';
      }

      // Ждем следующего кадра от JS
      var result = await new Promise(function(resolve) {
          setTimeout(() => {
              if (!shutdown) {
                  const c = document.createElement('canvas');
                  c.width = 640; c.height = 480;
                  c.getContext('2d').drawImage(video, 0, 0, 640, 480);
                  resolve(c.toDataURL('image/jpeg', 0.85));
              } else {
                  resolve('');
              }
          }, 50);
      });

      return {'img': result};
    }
    ''')
    display(js)

def get_frame(label, mask):
    return eval_js('stream_frame("{}", "{}")'.format(label, mask))

def js2img(js_reply):
    img_bytes = b64decode(js_reply.split(',')[1])
    nparr = np.frombuffer(img_bytes, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

# ================= MediaPipe =================
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)

def recognize_gesture(landmarks):
    def is_extended(tip, pip):
        return landmarks[tip].y < landmarks[pip].y

    # 👍 Распознавание большого пальца:
    # В зеркальном режиме камеры (facingMode: "user") большой палец 
    # при жесте "лайк" имеет меньшую координату X, чем основание
    thumb_extended = landmarks[4].x < landmarks[2].x
    
    fingers = [
        is_extended(8, 6),   # Указательный
        is_extended(12, 10), # Средний
        is_extended(16, 14), # Безымянный
        is_extended(20, 18)  # Мизинец
    ]
    count = sum(fingers)

    # 👇 НОВЫЙ ЖЕСТ: Лайк (большой палец вверх, остальные закрыты) → отправляем "loh"
    # Проверяем ПЕРЕД "back", чтобы избежать конфликта (оба имеют count == 0)
    if thumb_extended and count == 0:
        return "loh"
    
    # Остальные жесты
    if count == 4: return "stop"
    elif count == 0: return "back"  # Кулак — движение назад
    elif count == 1 and fingers[0]: return "forward"
    elif count == 2 and fingers[0] and fingers[1]: return "right"
    elif count == 3 and fingers[0] and fingers[1] and fingers[2]: return "left"
    return "none"

# ================= ЦИКЛ =================
init_webcam()
client = connect_mqtt()
time.sleep(2)

label_html = '👋 Show your hand...'
mask_img = ""
gesture_history = []
HISTORY_LEN = 5
last_command = ""

print("🚀 Запущено. Скелет руки будет отображаться поверх видео.")
try:
    while True:
        # Передаем текущую маску в JS для отображения
        js_reply = get_frame(label_html, mask_img)
        if not js_reply or not js_reply.get('img'):
            break

        img = js2img(js_reply['img'])
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = hands.process(img_rgb)

        current_gesture = "none"
        mask_img = ""  # Сброс

        if results.multi_hand_landmarks:
            lm = results.multi_hand_landmarks[0].landmark
            current_gesture = recognize_gesture(lm)

            # 👇 Рисуем скелет на кадре (толстые линии для лучшей видимости)
            mp_drawing.draw_landmarks(
                img,
                results.multi_hand_landmarks[0],
                mp_hands.HAND_CONNECTIONS,
                landmark_drawing_spec=mp_drawing_styles.get_default_hand_landmarks_style(),
                connection_drawing_spec=mp_drawing_styles.get_default_hand_connections_style()
            )

            # Кодируем кадр с маской в base64
            _, buffer = cv2.imencode('.jpg', img)
            mask_img = "data:image/jpeg;base64," + b64encode(buffer).decode('utf-8')

        gesture_history.append(current_gesture)
        if len(gesture_history) > HISTORY_LEN:
            gesture_history.pop(0)

        if len(gesture_history) == HISTORY_LEN:
            stable_gesture = max(set(gesture_history), key=gesture_history.count)

            if stable_gesture != "none" and stable_gesture != last_command:
                result = client.publish(TOPIC, stable_gesture)
                if result.rc == 0:
                    print(f"📡 Sent: `{stable_gesture}`")
                    last_command = stable_gesture
                    # 👇 Обновляем отображение статуса
                    if stable_gesture == "loh":
                        label_html = '👍 loh'
                    else:
                        label_html = f'🎯 {stable_gesture.upper()}'
                    mask_img = ""  # Скрываем маску на момент отправки

        time.sleep(0.08) # ~12 FPS

except KeyboardInterrupt:
    print("\n⏹ Остановлено")
finally:
    client.loop_stop()
    client.disconnect()
