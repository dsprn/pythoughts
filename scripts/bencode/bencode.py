import builtins

# ********** BENCODE TOKENS
SEPARATOR_TOKEN = b':'
INT_OPENING_TOKEN = b'i'
LIST_OPENING_TOKEN = b'l'
DICT_OPENING_TOKEN = b'd'
CLOSING_TOKEN = b'e'

# ********** ENCODING 
def encode_int(data: int) -> bytes:
    return INT_OPENING_TOKEN + bytes(str(data), 'utf-8') + CLOSING_TOKEN

def encode_str(data: str) -> bytes:
    return bytes(str(len(data)), 'utf-8') + SEPARATOR_TOKEN + bytes(data, 'utf-8')

def encode_list(data: list) -> bytes:
    res = b""
    for el in data:
        res += encode(el)
    return LIST_OPENING_TOKEN + res + CLOSING_TOKEN

def encode_dict(data: dict) -> bytes:
    res = b""
    for k, v in data.items():
        res += encode(k)
        res += encode(v)
    return DICT_OPENING_TOKEN + res + CLOSING_TOKEN

# encoding entry point
def encode(data) -> bytes:
    if type(data) == builtins.int:
        return encode_int(data)
    elif type(data) == builtins.str:
        return encode_str(data)
    elif type(data) == builtins.list:
        return encode_list(data)
    elif type(data) == builtins.dict:
        return encode_dict(data)
    else:
        raise ValueError("Tried to encode an unsupported type")

# ********** DECODING
# PURPOSE: convenience function used to mirror the encoding one, to maintain a coherent set of calls
def decode(data: bytes):
    return BencodedData(data).decode()

class BencodedData:
    def __init__(self, data: bytes):
        self._data = data
        self._idx = 0   # keeps track of what's been decoded and what's not

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        raise TypeError('Bencoded data cannot be changed')

    def __repr__(self):
        return f"BencodedData(idx={self._idx})"

    def _look_ahead(self):
        """look ahead to glance at the type"""
        if self._idx + 1 <= len(self._data):
            return self._data[self._idx:self._idx + 1]
        else:
            return b""

    def _move_forward_by(self, amount: int):
        self._idx += amount

    def _move_forward_to(self, idx: int):
        self._idx = idx
        
    def _find_forward(self, token: bytes) -> int:
        return self._data.index(token, self._idx)

    def _decode_int(self):
        """decode int and update the inner index"""
        # skip the opening token
        self._move_forward_by(1)
        # look for closing token
        till = self._find_forward(CLOSING_TOKEN)
        bi = int(self._data[self._idx:till])
        # move forward till the value after the integer closing token
        self._move_forward_to(till + 1)
        return bi

    def _decode_str(self):
        """decode whole string and update the inner index"""
        till = self._find_forward(SEPARATOR_TOKEN)
        str_length = self._data[self._idx:till]
        self._move_forward_by(len(str_length) + 1)
        # used to diffenciate between strings and non string bytes
        bs = self._data[self._idx : self._idx+int(str_length)]
        try:
            bs = bs.decode('utf-8')
        except UnicodeDecodeError:
            # entering here when trying to decode to utf-8 non unicode characters
            # namely, in this case, the torrent pieces binary hashes from 'pieces' in 'info' dict
            pass
        # move forward by the length of the string
        self._move_forward_by(int(str_length))
        return bs

    def _decode_list(self):
        """decode whole list and update the inner index"""
        bl = []
        # skip list opening token
        self._move_forward_by(1)
        while self._look_ahead() != CLOSING_TOKEN:
            bl.append(self.decode())
        # move forward by one to read the closing token
        self._move_forward_by(1)
        return bl

    def _decode_dict(self):
        """decode whole dict and update the inner index"""
        bd = {}
        # skip dict opening token
        self._move_forward_by(1)
        while self._look_ahead() != CLOSING_TOKEN:
            k = self.decode()
            v = self.decode()
            bd[k] = v
        # move forward by one to read the closing token
        self._move_forward_by(1)
        return bd

    def decode(self):
        next_value = self._look_ahead()
        if next_value == INT_OPENING_TOKEN:
            return self._decode_int()
        elif next_value == LIST_OPENING_TOKEN:
            return self._decode_list()
        elif next_value == DICT_OPENING_TOKEN:
            return self._decode_dict()
        elif next_value in b'0123456789':
            return self._decode_str()
