from packet import TrackerMessage, PeerRequest, PeerResponse, AckFile
from fileinfo import FileInfo
import peerutil 
from communication import send_data, retrieve_data
import sys, pickle, threading, queue, os, socket, time, struct, json, signal

SHARED_FILE_LOCATION = "Shared/"
CHUNK_SIZE = 512
BLOCK_SIZE = 100

tracker_address = sys.argv[1]
tracker_port = int(sys.argv[2])
min_alive_time = int(sys.argv[3])
tracker_socket_lock = threading.Lock()

hostname = socket.gethostname()
hostip = socket.gethostbyname(hostname)

file_object_table = {}
file_object_table_lock = threading.Lock()

localfiles = peerutil.get_local_fileinfo(SHARED_FILE_LOCATION, CHUNK_SIZE)
peerutil.open_local_files(localfiles, file_object_table, file_object_table_lock, SHARED_FILE_LOCATION)

# create socket and connection to tracker. 
# send files available for distribution from this client to tracker.
tracker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# tracker_socket.settimeout(5)
tracker_socket.connect((tracker_address, tracker_port))

# used to listen and handle file chunk requests.
upload_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
upload_socket.bind(('', 0))
upload_address = upload_socket.getsockname()

initmsg = vars(TrackerMessage.create_new_peer(localfiles, (hostip, upload_address[1])))
initmsg = json.dumps(initmsg).encode()
send_data(tracker_socket, tracker_socket_lock, initmsg)
current_id = int(retrieve_data(tracker_socket, tracker_socket_lock).decode())

initmsg = json.loads(retrieve_data(tracker_socket, tracker_socket_lock).decode())
files = initmsg['tracker_table']
files_lock = threading.Lock()

peers_table = initmsg['peers_table']
peers_table_lock = threading.Lock()

internal_file_status = peerutil.setup_local_file_status(localfiles)
internal_file_status_lock = threading.Lock()

# startup upload port
terminate_upload = False
terminate_upload_lock = threading.Lock()
upload_thread = threading.Thread(target = peerutil.upload_file, 
    args = (upload_socket, file_object_table, file_object_table_lock))
upload_thread.start()

threads = {}
threads_lock = threading.Lock()

files_active = set()
files_active_lock = threading.Lock()
while True:
    files_to_download = []
    files_lock.acquire()
    internal_file_status_lock.acquire()
    for f in files:
        if f not in internal_file_status:
            files_to_download.append(f)
            internal_file_status[f] = 0
    internal_file_status_lock.release()
    files_lock.release()
    # shutdown
    if len(files_to_download) == 0:
        time.sleep(min_alive_time)
        tracker_update = json.dumps(vars(TrackerMessage.create_table_update(None, None)))
        send_data(tracker_socket, tracker_socket_lock, tracker_update.encode())
        tracker_response = json.loads(retrieve_data(tracker_socket, tracker_socket_lock).decode())
        new_files = tracker_response['tracker_table']
        new_peers = tracker_response['peers_table']

        files_lock.acquire()
        internal_file_status_lock.acquire()
        for f in new_files:
            if f not in internal_file_status:
                files_to_download.append(f)
                internal_file_status[f] = 0
        internal_file_status_lock.release()
        # check everoyne done
        finished = True
        for f in new_files:
            numchunks = new_files[f]['numchunks']
            for id in new_files[f]['peers']:
                if new_files[f]['peers'][id]['downloaded_upto'] == numchunks:
                    finished = finished and True
                else:
                    finished = False
                    break
            if finished == False:
                break
        for f in new_files:
            files[f] = new_files[f]

        peers_table_lock.acquire()
        peers_table = new_peers
        peers_table_lock.release()
        files_lock.release()
        if len(files_to_download) == 0 and finished == True:
            break
    threads = []
    with files_active_lock:
        for f in files_to_download:
            t = threading.Thread(target = peerutil.download_file, args = (SHARED_FILE_LOCATION, f, files,
                files_lock, peers_table, peers_table_lock, internal_file_status, internal_file_status_lock, file_object_table,
                file_object_table_lock, files_active, files_active_lock, tracker_socket, tracker_socket_lock))
            threads.append(t)
            files_active.add(f)

    for t in threads:
        t.start()

    for t in threads:
        t.join()
    time.sleep(min_alive_time)

print('PEER %s SHUTDOWN: HAS%s' %(current_id, len(internal_file_status)))
for f in file_object_table:
    print('%s    %s' %(current_id, f))
    file_object_table[f].close()
    
send_data(tracker_socket, tracker_socket_lock, json.dumps(vars(TrackerMessage.create_exitcode())).encode())
tracker_socket.shutdown(socket.SHUT_WR)
tracker_socket.close()
os.kill(os.getpid(), signal.SIGTERM)