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
    "worker1": {"uid": 849156397443, "queue": Queue(), "is_working": False, "button_pin": 18, "last_press_time": 0},
    "worker2": {"uid": 543047530896, "queue": Queue(), "is_working": False, "button_pin": 19, "last_press_time": 0},
}

# 출근 상태 저장 (True: 출근, False: 퇴근)
attendance_states = {worker["uid"]: False for worker in workers.values()}

# 버튼 핀 설정
for worker in workers.values():
    GPIO.setup(worker["button_pin"], GPIO.IN, pull_up_down=GPIO.PUD_UP)

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
    버튼이 눌리면 호출되는 함수. 출근 상태와 큐 상태에 따라 메시지를 출력.
    """
    current_time = time.time()
    for worker_name, worker_data in workers.items():
        if channel == worker_data["button_pin"]:
            if current_time - worker_data["last_press_time"] < 0.3:  # 버튼 중복 입력 방지
                return
            worker_data["last_press_time"] = current_time

            if not attendance_states[worker_data["uid"]]:
                lcd.clear()
                lcd_message = "He didn't come"
                lcd.lcd_display_string(lcd_message, 1)
                print(f"{worker_name}: Didn't come")
                time.sleep(2)
                lcd.clear()
            else:
                if not worker_data["queue"].empty():
                    oldest_task = worker_data["queue"].get()
                    lcd.clear()
                    lcd_message = f"{worker_name}: done"
                    lcd.lcd_display_string(lcd_message, 1)
                    print(f"{worker_name} completed task: {oldest_task}")
                    time.sleep(2)
                    lcd.clear()

                    if worker_data["queue"].empty():
                        lcd.clear()
                        lcd_message = f"{worker_name}: no task"
                        lcd.lcd_display_string(lcd_message, 1)
                        print(f"{worker_name}: No task to complete")
                        time.sleep(2)
                        lcd.clear()
                else:
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

    lcd.clear()
    lcd_message = f"{assigned_worker}: + task"
    lcd.lcd_display_string(lcd_message, 1)
    print(f"{assigned_worker} assigned task: {task}")
    time.sleep(2)
    lcd.clear()

def toggle_work_state(uid):
    """
    RFID 태그를 통해 출퇴근 상태를 변경하고 LCD에 출력.
    """
    worker_name = None
    for name, data in workers.items():
        if data["uid"] == uid:
            worker_name = name
            break

    if not worker_name:
        lcd.clear()
        lcd.lcd_display_string("Unknown card", 1)
        print(f"Unknown UID: {uid}")
        time.sleep(2)
        lcd.clear()
        return

    attendance_states[uid] = not attendance_states[uid]

    if attendance_states[uid]:
        lcd.clear()
        lcd.lcd_display_string(f"{worker_name}: start", 1)
        print(f"{worker_name} - Work start for UID: {uid}")
    else:
        lcd.clear()
        lcd.lcd_display_string(f"{worker_name}: finish", 1)
        print(f"{worker_name} - Work finish for UID: {uid}")

    time.sleep(2)
    lcd.clear()

def read_tags_on_command():
    """
    사용자 명령에 따라 RFID 태그를 인식.
    """
    reader = SimpleMFRC522()
    try:
        while True:
            command = input("Enter 'detect' to read RFID or 'exit' to quit: ").strip().lower()
            if command == "detect":
                print("RFID 태그를 감지 중입니다. 태그를 스캔하세요...")
                try:
                    uid, text = reader.read()
                    print(f"RFID 태그 감지 완료! UID: {uid}")
                    toggle_work_state(uid)
                except Exception as e:
                    print(f"RFID 읽기 오류: {e}")
            elif command == "exit":
                print("RFID 태그 감지를 종료합니다.")
                break
            else:
                print("유효한 명령어를 입력하세요 ('detect' 또는 'exit').")
    except KeyboardInterrupt:
        print("\n프로그램 중단됨.")
    finally:
        GPIO.cleanup()
        print("GPIO 리소스를 정리했습니다.")

def receiver_thread(server_socket):
    """
    중앙 서버로부터 데이터를 수신하는 스레드.
    """
    while True:
        try:
            data = server_socket.recv(1024)
            if not data:
                print("서버 연결 종료")
                break

            msg = Message.deserialize(data)
            if msg.type == MessageType.WORK_ORDER:
                assign_task(msg.content)
        except ConnectionResetError:
            print("서버와의 연결이 끊어졌습니다. 다시 연결을 시도합니다.")
            break
        except Exception as e:
            print(f"수신 스레드 오류: {e}")
            break

def main():
    try:
        central_socket = create_and_connect_socket(CENTRAL_SERVER_IP, CENTRAL_SERVER_PORT)
        print("중앙 서버에 연결 성공")

        identification_msg = Message(
            type=MessageType.WORK_ORDER,
            send_type=SendType.SEND_FROM_WORKER,
            content="worker_management"
        )
        central_socket.send(identification_msg.serialize())
        print("작업자 식별 메시지 전송 완료")

        tag_thread = threading.Thread(target=read_tags_on_command, daemon=True)
        tag_thread.start()

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
