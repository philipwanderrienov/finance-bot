import socket

for host in ["localhost", "127.0.0.1"]:
    try:
        infos = socket.getaddrinfo(host, 5432, type=socket.SOCK_STREAM)
        print(host, [info[4][0] for info in infos])
    except Exception as exc:
        print(host, "ERR", exc)
