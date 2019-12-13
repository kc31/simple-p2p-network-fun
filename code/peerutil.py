from fileinfo import FileInfo
from packet import TrackerMessage, AckFile
from communication import send_data, retrieve_data
from packet import PeerRequest, PeerResponse
import os, json, time, socket, struct, threading, signal

def get_local_fileinfo(directory, chunksize):
    local_filenames = os.listdir(directory)
    localfiles = {}

    for name in local_filenames:
        filesize = os.path.getsize(directory + name)
        numchunks = 0
        
        if filesize % chunksize != 0:
            numchunks = filesize // chunksize + 1
        else:
            numchunks = filesize // chunksize
        filedata = FileInfo.create_new_fileinfo(name, filesize, numchunks)
        localfiles[name] = vars(filedata)
    return localfiles

def open_local_files(localfiles, file_object_table, file_lock, directory):
    file_lock.acquire()
    for fname in localfiles:
        file_object_table[fname] = open(directory + fname, 'ab+')
    file_lock.release()

def setup_local_file_status(localfiles):
    d = {}
    for f in localfiles:
        d[f] = localfiles[f]['numchunks']
    return d

def send_ack(tracker_socket, tracker_port_lock, filename, numchunk, current_id):
    message = vars(TrackerMessage.create_ack(
        vars(AckFile(filename, numchunk, current_id))))
    message = json.dumps(message).encode()
    send_data(tracker_socket, tracker_port_lock, message)

def upload_file(upload_socket, file_object_table, file_object_table_lock):
    while True:
        message, address = upload_socket.recvfrom(2048)
        message = json.loads(message.decode())
        fname = message['filename']
        frange = message['data_range']
        file_object_table_lock.acquire()
        file_requested = file_object_table[fname]
        file_object_table_lock.release()

        data = b''
        for i in range(frange[0], frange[1]):
            file_requested.seek(i * 512)
            chunk = file_requested.read(512)
            data = data + chunk
        response = PeerResponse(frange, data).get_udp_data()
        upload_socket.sendto(response, address)

def download_file(directory, filename, files, files_lock, peers_table,
    peers_table_lock, internal_file_status, internal_file_status_lock, file_object_table,
    file_object_table_lock, files_active, files_active_lock, tracker_socket, tracker_socket_lock):

    with internal_file_status_lock:
        current_chunk = internal_file_status[filename]

    with files_lock:
        fnumchunks = files[filename]['numchunks']

    with file_object_table_lock:
        if filename not in file_object_table:
            file_object_table[filename] = open(directory + filename, 'a+b')
        file_object = file_object_table[filename]

    download_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    download_socket.bind(('',0))
    download_socket.settimeout(5)
    
    best_peer_id = -1 
    peer_status = -1
    for id in files[filename]['peers']:
        if peer_status < files[filename]['peers'][id]['downloaded_upto']:
            best_peer_id = id
            peer_status = files[filename]['peers'][id]['downloaded_upto']
    address = (peers_table[best_peer_id]['address'], peers_table[best_peer_id]['port'])

    BLOCK_SIZE = 100

    buffer = {}
    while current_chunk <= fnumchunks:
        threads = []
        x = min(fnumchunks + 1, current_chunk + BLOCK_SIZE)
        request = vars(PeerRequest(filename, [current_chunk, x]))
        download_socket.sendto(json.dumps(request).encode(), address)
        
        # simple reliability
        buffer_key = (current_chunk, x)
        get_file = False
        while get_file == False:
            if buffer_key in buffer:
                stored_data = buffer[buffer_key]
                file_object.write(stored_data)
                get_file = True
                del buffer[buffer_key]
                break
            else:
                try:
                    response = download_socket.recv(65535)
                    response = PeerResponse.parse_udp_data(response)
                    if response.data_range[0] == current_chunk and response.data_range[1] == x:
                        file_object.write(response.data)
                        file_object.flush()
                        get_file = True
                        break
                    else:
                        out_of_order_key = (response.data_range[0], response.data_range[1])
                        buffer[out_of_order_key] = response.data
                except socket.timeout:
                    download_socket.sendto(json.dumps(request).encode(), address)

        current_chunk = response.data_range[1]

        with internal_file_status_lock:
            internal_file_status[filename] = current_chunk - 1
        
        update = vars(TrackerMessage.create_ack(vars(AckFile(filename, current_chunk - 1, None))))
        send_data(tracker_socket, tracker_socket_lock, json.dumps(update).encode())
        
        rawdata = retrieve_data(tracker_socket, tracker_socket_lock)
        newdata = json.loads(rawdata.decode())

        new_table = newdata['tracker_table']
        new_peers = newdata['peers_table']

        with files_lock:
            for f in new_table:
                if f in files:
                    files[f] = new_table[f]
                else:
                    with files_active_lock:
                        files_active.add(f)
                        files[f] = new_table[f]
                        with internal_file_status_lock:
                            internal_file_status[f] = 0
                        
                        t = threading.Thread(target = download_file, 
                            args = (directory, f, files, files_lock, peers_table,
                                peers_table_lock, internal_file_status, internal_file_status_lock, file_object_table,
                                file_object_table_lock, files_active, files_active_lock, tracker_socket, tracker_socket_lock))
                        threads.append(t)

            with peers_table_lock:
                for p in new_peers:
                    peers_table[p] = new_peers[p]
        for t in threads:
            t.start()   
    for t in threads:
            t.join()
    return     
    