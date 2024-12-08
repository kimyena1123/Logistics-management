import socket

def create_and_bind_socket(port):
    """서버 소켓을 생성하고 바인딩"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 포트 재사용 옵션 설정
    server_socket.bind(('', port))
    server_socket.listen(5)
    return server_socket

def create_and_connect_socket(ip, port):
    """클라이언트 소켓을 생성하고 서버에 연결"""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((ip, port))
    return client_socket
