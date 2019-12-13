import struct
def send_data(tcpsocket, payload):
    size = len(payload)
    size_in_bytes = size.to_bytes(length = 4, byteorder = "big")
    tcpsocket.send(size_in_bytes + payload)

def retrieve_data(tcpsocket):
    b = b''
    while len(b) < 4:
        b = b + tcpsocket.recv(4 - len(b))
    
    # size = int.from_bytes(struct.unpack("!I", b)[0], byteorder = 'big')
    # size = struct.unpack("!I", b)[0]
    size = int.from_bytes(b, byteorder = "big")
    # data = bytearray()
    # while len(data) < size:
    #     data = data + tcpsocket.recv(size - len(data))

    data = bytearray()
    while len(data) < size:
        packet = tcpsocket.recv(size - len(data))
        data.extend(packet)
    return data
