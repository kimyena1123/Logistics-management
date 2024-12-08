import RPi.GPIO as GPIO
import socket
import threading
from common import Message, MessageType, SendType, CENTRAL_SERVER_PORT
from socket_util import create_and_bind_socket


# 글로벌 변수
worker_socket = None
inventory = {"A 구역": 0, "B 구역": 0}  # 각 구역의 재고 상태
led_pins = {"A 구역": 27, "B 구역": 5}  # 각 구역의 LED 핀

# GPIO 초기화
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
for pin in led_pins.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)  # 초기 LED 꺼짐 상태

def update_led(zone):
    """재고 상태에 따라 LED를 켜거나 끄는 함수."""
    if inventory[zone] < 3:
        GPIO.output(led_pins[zone], GPIO.HIGH)  # LED 켜기
        print(f"{zone} LED 켜짐 (재고: {inventory[zone]})")
    else:
        GPIO.output(led_pins[zone], GPIO.LOW)  # LED 끄기
        print(f"{zone} LED 꺼짐 (재고: {inventory[zone]})")

def handle_inventory_update(msg):
    """재고 업데이트를 처리하는 함수."""
    try:
        zone, quantity = msg.content.split(":")
        zone = zone.strip()
        quantity = int(quantity.strip())

        if zone in inventory:
            inventory[zone] = quantity
            print(f"{zone} 재고 업데이트: {quantity}")
            update_led(zone)
        else:
            print(f"알 수 없는 구역: {zone}")
    except Exception as e:
        print(f"재고 업데이트 처리 오류: {e}")

def send_work_order(target_socket, msg):
    if target_socket:
        try:
            target_socket.send(msg.serialize())
            print(f"작업 지시 전송: {msg.content}")
        except Exception as e:
            print(f"작업 지시 전송 오류: {e}")
    else:
        print("작업자 소켓이 설정되지 않았습니다. 작업 지시를 보낼 수 없습니다.")

def receiver_data(client_socket, addr):
    global worker_socket
    print(f"연결 수락됨: {addr}")

    while True:
        try:
            data = client_socket.recv(1024)
            if not data:
                print(f"클라이언트 연결 종료: {addr}")
                break

            msg = Message.deserialize(data)

            if msg.send_type == SendType.SEND_FROM_WORKER:
                worker_socket = client_socket
                print("작업자 소켓 설정 완료")  # 작업자 소켓 설정

            elif msg.type in (MessageType.INVENTORY_UPDATE_FROM_WARE, MessageType.INVENTORY_UPDATE_FROM_WORKER):
                handle_inventory_update(msg)
            elif msg.type == MessageType.WORK_ORDER:
                send_work_order(worker_socket, msg)
            else:
                print(f"알 수 없는 메시지 수신: {msg.content}")
        except Exception as e:
            print(f"데이터 수신 오류: {e}")
            break

if __name__ == "__main__":
    try:
        central_socket = create_and_bind_socket(CENTRAL_SERVER_PORT)
        print("서버가 시작되었습니다.")

        while True:
            try:
                client_conn, addr = central_socket.accept()

                # 로컬호스트 연결을 무조건 무시하지 않음
                if addr[0] == "127.0.0.1":
                    print("로컬호스트 연결 수락됨")

                threading.Thread(target=receiver_data, args=(client_conn, addr)).start()
            except Exception as e:
                print(f"연결 처리 오류: {e}")
    finally:
        GPIO.cleanup()
