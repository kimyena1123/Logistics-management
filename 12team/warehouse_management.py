import socket
import time
from common import Message, MessageType, SendType, CENTRAL_SERVER_IP, CENTRAL_SERVER_PORT
from socket_util import create_and_connect_socket

# 예제 데이터: 각 구역별 센서와 수기 입력 데이터를 가져오는 함수
def get_sensor_data(zone):
    """각 구역(A, B)의 센서 데이터를 가져오는 함수"""
    # 실제 프로젝트에서는 각 구역별 센서 데이터를 받아야 함
    return 100 if zone == "A" else 200  # 임의 값

def get_manual_data(zone):
    """각 구역(A, B)의 수기 데이터를 가져오는 함수"""
    # 실제 프로젝트에서는 각 구역별 수기 데이터를 받아야 함
    return 90 if zone == "A" else 195  # 임의 값

def update_inventory(server_socket, zone, updated_inventory):
    """특정 구역의 재고 데이터를 업데이트하도록 서버에 전송."""
    msg = Message(
        type=MessageType.INVENTORY_UPDATE_FROM_WARE,
        send_type=SendType.SEND_FROM_WAREHOUSE,
        content=f"{zone}구역: {updated_inventory}",
    )
    server_socket.send(msg.serialize())
    print(f"{zone}구역 재고 업데이트 완료")

def compare_inventory_and_notify(server_socket, zone):
    """특정 구역의 센서 데이터와 수기 데이터를 비교하고, 더 작은 재고로 업데이트 후 업무 지시."""
    sensor_data = get_sensor_data(zone)
    manual_data = get_manual_data(zone)

    if sensor_data != manual_data:
        # 더 작은 값으로 재고 업데이트
        updated_inventory = min(sensor_data, manual_data)
        update_inventory(server_socket, zone, updated_inventory)

        # 차이에 대한 업무 지시 전송
        message_content = (
            f"{zone}구역 재고 불일치"
        )
        msg = Message(
            type=MessageType.WORK_ORDER,
            send_type=SendType.SEND_FROM_WAREHOUSE,
            content=message_content,
        )
        server_socket.send(msg.serialize())
        print(f"업무 지시 전송 완료")
    else:
        print(f"{zone}구역 재고 데이터가 일치합니다. 추가 작업 필요 없음.")

if __name__ == "__main__":
    server_socket = create_and_connect_socket(CENTRAL_SERVER_IP, CENTRAL_SERVER_PORT)
    
    # 각 구역의 이전 상태를 저장할 변수
    previous_sensor_data = {"A": None, "B": None}
    previous_manual_data = {"A": None, "B": None}

    try:
        while True:
            # A구역과 B구역의 재고를 각각 확인
            for zone in ["A", "B"]:
                # 현재 센서 및 수기 데이터를 가져오기
                sensor_data = get_sensor_data(zone)
                manual_data = get_manual_data(zone)

                # 이전 상태와 비교하여 변화가 있는지 확인
                if (sensor_data != previous_sensor_data[zone] or 
                    manual_data != previous_manual_data[zone]):
                    compare_inventory_and_notify(server_socket, zone)

                    # 이전 상태를 업데이트
                    previous_sensor_data[zone] = sensor_data
                    previous_manual_data[zone] = manual_data

            # 주기적으로 감지 (5초 대기)
            time.sleep(5)

    except KeyboardInterrupt:
        print("프로그램 종료 요청.")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        server_socket.close()
