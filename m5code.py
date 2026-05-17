from m5stack import *
from m5ui import *
from uiflow import *
from m5mqtt import M5mqtt
import time


base_x = module.get(module.BASE_X)
# Настройка экрана (для отладки)
setScreenColor(0x111111)
label0 = M5TextBox(10, 10, "MQTT Status: Disconnected", lcd.FONT_Default, 0xFFFFFF, rotate=0)

# Функция-обработчик входящих сообщений
def fun_mqtt_callback(topic_data):
    # topic_data — это полезная нагрузка (payload) сообщения
    msg = str(topic_data)
    print("Received msg:", msg)

    # Логика выполнения команд
    if msg == "back":
      base_x.set_motor_speed(2, -20)
      base_x.set_motor_speed(3, -20)
    elif msg == "stop":
      base_x.set_motor_speed(3, 0)
      base_x.set_motor_speed(2, 0)
    elif msg == "forward":# Выключить свет
        base_x.set_motor_speed(1, 50)
        wait(1)
        base_x.set_motor_speed(1, 0)
    elif msg == "right":# Выключить свет
        base_x.set_motor_speed(1, -50)
        wait(1)
        base_x.set_motor_speed(1, 0)
    elif msg == "loh":# Выключить свет
        base_x.set_motor_speed(2, 20)
        base_x.set_motor_speed(3, 20)
    else:
        label0.setText("Unknown msg: " + msg)

# Инициализация MQTT клиента
# Параметры: client_id, server, port, user, password, keepalive
client = M5mqtt('m5stack_device_001', 'broker.emqx.io', 1883, '', '', 300)

# Подписка на топик и привязка функции обработки
client.subscribe(str('ligarobotov/darkfaerie'), fun_mqtt_callback)

# Запуск подключения
label0.setText("MQTT Status: Connecting...")
client.start()
label0.setText("MQTT Status: Connected")

# Основной цикл программы
while True:
    # Здесь можно добавить другие задачи, клиент работает в фоне
    wait_ms(100)
