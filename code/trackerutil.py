import fileinfo
import pickle, threading, socket, time, sys, json

from fileinfo import FileInfo, PeerStatus
from communication_tracker import send_data, retrieve_data
from packet import PeerInfo, TrackerMessage

def send_table(files, files_lock, peers, peers_lock, client_socket):
    with files_lock:
        with peers_lock:
            send_data(client_socket, json.dumps(vars(TrackerMessage.create_table_update(files, peers))).encode())

def ack_handler(data, current_id, files, files_lock, client_socket, peers, peers_lock):
    with files_lock:
        files[data['filename']]['peers'][current_id]['downloaded_upto'] = data['chunk_num']
        with peers_lock:
            send_data(client_socket, json.dumps(vars(TrackerMessage.create_table_update(files, peers))).encode())

def peer_exit_handler(current_id, files, files_lock, peers, peers_lock, print_lock):
    with files_lock:
        owned_files = []
        dead_files = []
        for f in files:
            del files[f]['peers'][current_id]
            owned_files.append(f)
            if len(files[f]['peers']) == 0:
                dead_files.append(f)
        for f in dead_files:
            del files[f]
        with peers_lock:
            del peers[current_id]
    with print_lock:
        print('PEER %s DISCONNECT: RECEIVED %s' %(current_id, len(owned_files)))
        for f in owned_files:
            print('%s    %s' %(current_id, f))
        

def client_thread(print_lock, client_socket, client_address, peers_counter, peers, peers_lock,
    files, files_lock):
    with peers_lock:
        current_id = peers_counter[0]
        peers_counter[0] = peers_counter[0] + 1

    data = retrieve_data(client_socket).decode()
    data = json.loads(data)
    newfiles = data['newfiles']

    with print_lock:
        print('PEER %s CONNECT: OFFERS %s' %(current_id, len(newfiles)))
        for f in newfiles:
            print('%s    %s %s' %(current_id, f, newfiles[f]['numchunks']))

    send_data(client_socket, str(current_id).encode())

    files_lock.acquire()
    peers_lock.acquire()
    peers[current_id] = vars(PeerInfo(data['uploadaddress'][0], data['uploadaddress'][1]))
    # peers[current_id] = vars(PeerInfo(client_address[0], data['uploadaddress'][1]))
    # Go through existing files, mark the new peer has a progress of 0.
    for f in files:
        files[f]['peers'][current_id] = vars(fileinfo.PeerStatus.create_peerstatus(current_id, 0))

    for f in newfiles:
        peer_status_for_f = {}
        for p in peers:
            if p == current_id:
                peer_status_for_f[p] = vars(PeerStatus(p, newfiles[f]['numchunks']))
            else:
                peer_status_for_f[p] = vars(PeerStatus(p, 0))
        finfo = vars(FileInfo.create_tracker_record(f, newfiles[f]['filesize'], 
                                                    newfiles[f]['numchunks'], peer_status_for_f))
        files[f] = finfo
    peers_lock.release()
    files_lock.release()

    # bootstrap new peer
    send_table(files, files_lock, peers, peers_lock, client_socket)

    while True:
        data = retrieve_data(client_socket)
        data = json.loads(data.decode())
        message_type = int(data['message_type'])

        if message_type == TrackerMessage.PEER_ACK:
            data = data['ack']
            ack_handler(data, current_id, files, files_lock, client_socket, peers, peers_lock)
        elif message_type == TrackerMessage.PEER_EXIT:
            peer_exit_handler(current_id, files, files_lock, peers, peers_lock, print_lock)
            return
        elif message_type == TrackerMessage.TRACKER_TO_PEER_CODE:
            send_table(files, files_lock, peers, peers_lock, client_socket)
