import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
from queue import Queue
import threading
import socket
from smbus2 import SMBus
import time
from common import Message, MessageType, SendType, CENTRAL_SERVER_IP, CENTRAL_SERVER_PORT
from socket_util import create_and_connect_socket

# GPIO 초기화
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

# 작업자 정보
workers = {
    "worker1": {"uid": 849156397443, "queue": Queue(), "is_working": False, "button_pin": 18},
    "worker2": {"uid": 849156397444, "queue": Queue(), "is_working": False, "button_pin": 19},
}

# UID 상태 저장
card_states = {}

# 버튼 핀 설정
for worker in workers.values():
    GPIO.setup(worker["button_pin"], GPIO.IN, pull_up_down=GPIO.PUD_UP)  # 버튼 핀을 입력으로 설정

# LCD 클래스 정의
class LCD:
    def __init__(self, addr=0x27, bus=1):
        self.addr = addr
        self.bus = SMBus(bus)
        self.lcd_init()

    def lcd_init(self):
        self.lcd_write(0x33)
        self.lcd_write(0x32)
        self.lcd_write(0x06)
        self.lcd_write(0x0C)
        self.lcd_write(0x28)
        self.lcd_write(0x01)
        time.sleep(0.05)

    def lcd_write(self, cmd, mode=0):
        high = mode | (cmd & 0xF0) | 0x08
        low = mode | ((cmd << 4) & 0xF0) | 0x08
        self.bus.write_byte(self.addr, high)
        self.lcd_toggle_enable(high)
        self.bus.write_byte(self.addr, low)
        self.lcd_toggle_enable(low)

    def lcd_toggle_enable(self, data):
        time.sleep(0.0005)
        self.bus.write_byte(self.addr, (data | 0x04))
        time.sleep(0.0005)
        self.bus.write_byte(self.addr, (data & ~0x04))
        time.sleep(0.0005)

    def lcd_display_string(self, string, line):
        if line == 1:
            self.lcd_write(0x80)
        elif line == 2:
            self.lcd_write(0xC0)
        for char in string:
            self.lcd_write(ord(char), 0x01)

    def clear(self):
        self.lcd_write(0x01)

# LCD 객체 생성
lcd = LCD()

def handle_button_press(channel):
    """
    버튼이 눌리면 호출되는 함수. LCD에 완료 메시지를 출력하고 작업 상태를 완료로 변경.
    """
    for worker_name, worker_data in workers.items():
        if channel == worker_data["button_pin"]:
            if not worker_data["queue"].empty():
                # 업무가 존재하면 작업 완료 처리
                completed_task = worker_data["queue"].get()
                lcd.clear()
                lcd_message = f"{worker_name}: finish"
                lcd.lcd_display_string(lcd_message, 1)
                print(f"{worker_name} completed task: {completed_task}")
                time.sleep(2)
                lcd.clear()
            else:
                # 작업이 없는 경우
                lcd.clear()
                lcd_message = f"{worker_name}: no task"
                lcd.lcd_display_string(lcd_message, 1)
                print(f"{worker_name}: No task to complete")
                time.sleep(2)
                lcd.clear()

# 버튼 이벤트 핸들러 설정
for worker in workers.values():
    GPIO.add_event_detect(worker["button_pin"], GPIO.FALLING, callback=handle_button_press, bouncetime=300)

def assign_task(task):
    """
    작업자에게 업무를 할당하고 LCD에 작업자를 표시.
    """
    worker1_tasks = workers["worker1"]["queue"].qsize()
    worker2_tasks = workers["worker2"]["queue"].qsize()

    if worker1_tasks <= worker2_tasks:
        workers["worker1"]["queue"].put(task)
        assigned_worker = "worker1"
    else:
        workers["worker2"]["queue"].put(task)
        assigned_worker = "worker2"

    # LCD 업데이트
    lcd.clear()
    lcd_message = f"{assigned_worker}: work add"
    lcd.lcd_display_string(lcd_message, 1)
    print(f"{assigned_worker} assigned task: {task}")
    time.sleep(2)
    lcd.clear()

def toggle_work_state(uid):
    """
    RFID 태그를 통해 출퇴근 상태를 변경하고 LCD에 출력.
    """
    if uid not in card_states:
        card_states[uid] = True
    if card_states[uid]:
        lcd.clear()
        lcd.lcd_display_string("Work start", 1)
        print(f"Work start for UID: {uid}")
    else:
        lcd.clear()
        lcd.lcd_display_string("Work finish", 1)
        print(f"Work finish for UID: {uid}")
    time.sleep(2)
    lcd.clear()
    card_states[uid] = not card_states[uid]

def read_tags():
    """
    RFID 태그를 지속적으로 읽음.
    """
    try:
        reader = SimpleMFRC522()
        while True:
            print("Waiting for an RFID card...")
            uid, text = reader.read()
            print(f"Card detected! UID: {uid}")
            toggle_work_state(uid)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nProgram interrupted.")
    finally:
        GPIO.cleanup()

def receiver_thread(server_socket):
    """
    중앙 서버로부터 데이터를 수신하는 스레드.
    """
    while True:
        try:
            data = server_socket.recv(1024)
            if not data:
                print("데이터 수신 오류 또는 연결 종료")
                break

            msg = Message.deserialize(data)
            if msg.type == MessageType.WORK_ORDER:
                assign_task(msg.content)
        except Exception as e:
            print(f"수신 스레드 오류: {e}")
            break

def main():
    try:
        # 중앙 서버와 연결
        central_socket = create_and_connect_socket(CENTRAL_SERVER_IP, CENTRAL_SERVER_PORT)
        print("중앙 서버에 연결 성공")

        # 자신을 작업자로 식별하는 메시지 전송
        identification_msg = Message(
            type=MessageType.WORK_ORDER,
            send_type=SendType.SEND_FROM_WORKER,
            content="worker_management"
        )
        central_socket.send(identification_msg.serialize())
        print("작업자 식별 메시지 전송 완료")

        # RFID 태그 읽기 스레드 시작
        tag_thread = threading.Thread(target=read_tags, daemon=True)
        tag_thread.start()

        # 수신 스레드 실행
        recv_thread = threading.Thread(target=receiver_thread, args=(central_socket,))
        recv_thread.start()

        recv_thread.join()
        tag_thread.join()
        central_socket.close()
    except Exception as e:
        print(f"메인 함수 오류: {e}")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
