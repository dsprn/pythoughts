import unittest
from bencode import encode, decode


class TestEncoding(unittest.TestCase):
    def test_int(self):
        self.assertEqual(encode(42), 
                         b"i42e")

    def test_str(self):
        self.assertEqual(encode("snake river"), 
                         b"11:snake river")

    def test_list(self):
        self.assertEqual(encode(["snake river", 42]),
                         b"l11:snake riveri42ee")

    def test_bdict(self):
        self.assertEqual(encode({42: "answer", "less": "is more"}),
                         b"di42e6:answer4:less7:is moree")


class TestDecoding(unittest.TestCase):
    def test_int(self):
        self.assertEqual(decode(b"i42e"),
                         42)
    
    def test_str(self):
        self.assertEqual(decode(b"11:snake river"),
                         "snake river")
    
    def test_list(self):
        self.assertEqual(decode(b"l11:snake riveri42ee"),
                         ["snake river", 42])
    
    def test_bdict(self):
        self.assertEqual(decode(b"di42e6:answer4:less7:is moree"),
                         {42: "answer", "less": "is more"})


if __name__ == "__main__":
    unittest.main()
