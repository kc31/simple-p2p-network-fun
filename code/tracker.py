import packet
import fileinfo
import pickle, threading, socket, time, sys

from trackerutil import client_thread

# lock to enforce synchronous printing
print_lock = threading.Lock()

# setup server socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 0))
s.listen(5)
server_address = s.getsockname()
#print(str(server_address[1]))
port_file = open('port.txt', 'w')
port_file.write(str(server_address[1]))
port_file.flush()
port_file.close()

# peer info
# key = counter for this peer. value = PeerInfo for that peer.
peers_counter = [0]
peers = {}
peers_lock = threading.Lock()

# file info, dictionary key = filename, value = fileinfo object for that file.
# see fileinfo.py
files = {}
files_lock = threading.Lock()

while True:
    c, address = s.accept()
    cthread = threading.Thread(target = client_thread, 
        args = (print_lock, c, address, peers_counter, peers, peers_lock, files,
        files_lock))
    cthread.start()
