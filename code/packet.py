import fileinfo
import struct

# used by peers to message peers, request filename and that chunk
class PeerRequest:
    # filename = file requested
    # data_range = chunks in the data range sequentially
    def __init__(self, filename, data_range):
        self.filename = filename
        self.data_range = data_range

# used by peers to respond to peer's request. returns data
class PeerResponse:
    MAX_LENGTH_UDP = 65535
    # range = range of the chunks of the data.
    # ie: range = [1, 3] means chunks 1 to 3 is in data,
    def __init__(self, data_range, data):
        if len(data) > PeerResponse.MAX_LENGTH_UDP:
            raise Exception("Data too large (max 65535 char): ", len(data))
        self.data_range = data_range
        self.data = data
  
    def get_udp_data(self):
        b = struct.pack("!II", self.data_range[0], self.data_range[1]) + self.data
        return b

    @staticmethod
    def parse_udp_data(data):
        left = struct.unpack("!I", data[:4])[0]
        right = struct.unpack("!I", data[4:8])[0]
        data_range = [left, right]
        payload = data[8:]
        return PeerResponse(data_range, payload)

# Object to represent a peer has successfully downloaded a chunk
# sent to file
class AckFile:
    def __init__(self, filename, chunk_num, peer_id):
        self.filename = filename
        self.chunk_num = chunk_num
        self.peer_id = peer_id

# Object used to represent a peer's address
class PeerInfo:
    # address: the address of this peer
    # port: the port of this peer.
    def __init__(self, address, port):
        self.address = address
        self.port = port

class TrackerMessage:
    # message_types
    # 1 = Tracker to peer, informing it should update table. 
    # 2 = new peer to tracker, informing of its new files
    # 3 = existing peer to tracker, informing its downloaded some file.
    # 4 = peer exit
    TRACKER_TO_PEER_CODE = 1
    NEW_PEER_TO_TRACKER = 2
    PEER_ACK = 3
    PEER_EXIT = 4

    # tracker_table = dictionary of (filename, FileInfo)
    # peers_table = dictionary of(peer_id, PeerInfo)
    # newfiles = dict of (filename, fileinfo)
    # ack = dict of (filename, tuple representing chunk range downloaded)
    # uploadaddress = [address, port]

    # ack = ack message for file 
    def __init__(self, message_type, tracker_table = None, peers_table = None, newfiles = None, ack = None, uploadaddress = None):
        self.message_type = message_type
        self.tracker_table = tracker_table
        self.peers_table = peers_table
        self.newfiles = newfiles
        self.ack = ack
        self.uploadaddress = uploadaddress
    
    @staticmethod
    def create_table_update(tracker_table, peers_table):
        return TrackerMessage(TrackerMessage.TRACKER_TO_PEER_CODE, tracker_table = tracker_table, peers_table = peers_table)
    
    @staticmethod
    def create_new_peer(newfiles, address):
        return TrackerMessage(TrackerMessage.NEW_PEER_TO_TRACKER, newfiles = newfiles, uploadaddress = address)
    
    @staticmethod
    def create_ack(ack):
        return TrackerMessage(TrackerMessage.PEER_ACK, ack = ack)
    
    @staticmethod
    def create_exitcode():
        return TrackerMessage(TrackerMessage.PEER_EXIT)
    