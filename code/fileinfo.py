class FileInfo:
    # filename: name of file this object corresponds to
    # filesize: size of file this object corresponds to
    # numchunks: filesize / 512 bytes
    # peers: dict of (peer_id, PeerStatus objects)
    def __init__(self, filename, filesize, numchunks, peers):
        self.filename = filename
        self.filesize = filesize
        self.numchunks = numchunks
        self.peers = peers

    @staticmethod
    def create_new_fileinfo(filename, filesize, numchunks):
        return FileInfo(filename, filesize, numchunks, {})
    
    @staticmethod
    def create_tracker_record(filename, filesize, numchunks, peers):
        return FileInfo(filename, filesize, numchunks, peers)
        

class PeerStatus:
    # identifier: the unique identifier for this peer.
    def __init__(self, identifier, downloaded_upto):
        self.identifier = identifier
        self.downloaded_upto = downloaded_upto
    @staticmethod
    def create_peerstatus(identifier, downloaded_upto):
        return PeerStatus(identifier, downloaded_upto)
    