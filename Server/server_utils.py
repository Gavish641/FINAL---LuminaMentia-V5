import sqlite3 # for database
import json
import random # for sorting numbers and make a random key for encryption
# Encryption
from cryptography.fernet import Fernet
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA


class UsersDB:

    def __init__(self):
        """
        Initialize the class by setting up the database file and encryption.
        """
        self.database = 'users.db'
        self.encryption = Encryption()

    def connect_to_db(self):
        """
        Connects to the specified database and returns the connection object.
        """
        conn = sqlite3.connect(self.database)
        return conn

    def create_table(self):
        """
        Creates a table named 'users' in the database if it doesn't already exist. 
        The table has columns for username, password, remember_me flag, and mac_address.         
        """
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY NOT NULL, 
                password TEXT NOT NULL,
                remember_me INTEGER,
                mac_address TEXT
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()

    def insert_user(self, username, password, remember_me, mac_address):
        """
        A function to insert a new user into the database with the provided username, password, remember_me option, and mac address.
        Parameters:
            username (str): The username of the new user.
            password (str): The password of the new user (in JSON format, encrypted, hashed).
            remember_me (int): Flag indicating if the user wants to be remembered (True -> 1, False -> 0).
            mac_address (str): The mac address of the new user (hashed).
        """
        mac_address2 = (mac_address)
        remember_me = int(remember_me)
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO users (username, password, remember_me, mac_address) VALUES (?, ?, ?, ?)''', (username, str(password), int(remember_me), mac_address2))
        conn.commit()
        cursor.close()
        conn.close()

    def check_user_registered(self, username):
        """
        Check if the user with the given username is registered in the database.
        Parameter: username: str - the username to check for registration
        return: bool - True if the user is registered, False otherwise
        """
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM users WHERE username=(?)''', (username,))
        result = cursor.fetchone() is not None
        conn.commit()
        cursor.close()
        conn.close()
        return result
        # returns true or false
    
    def try_login(self, username, password_data, encryption_key):
        """
        Try to log in a user with the provided username and password data.
        Parameters:
            username: The username of the user trying to log in.
            password_data: A list containing the encrypted password, salt, nonce, and tag (decryption requirements).
        return: True if the entered password matches the stored password, False otherwise.
        """
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT password FROM users WHERE username=(?)''', (username,))
        result = cursor.fetchone()[0]
        decrypted_stored_password = self.encryption.decrypt_data(eval(password_data), encryption_key)  # Retrieve the stored encrypted password
        if str(result) == str(decrypted_stored_password):
            login_result = True
        else:
            login_result = False
        cursor.close()
        conn.close()
        return login_result
    
    def check_remember_me(self, username):
        """
        Check if the user is saved as remembered and return the result.
        Parameters:
            username (str): The username of the user
        Returns:
            bool: The result of the remember me check (True -> 1, False -> 0)
        """
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT remember_me FROM users WHERE username=(?)''', (username,))
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return result

    def remember_me_on(self, mac_address, username):
        """
        Updates the 'remember_me' and 'mac_address' fields in the 'users' table for the given username.
        The 'remember_me' field is set to True and the 'mac_address' field is set to the provided 'mac_address'.
        Parameters:
            mac_address (str): The MAC address to be updated.
            username (str): The username for which the 'remember_me' and 'mac_address' fields are to be updated.
        """
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET remember_me=(?), mac_address=(?) WHERE username=(?)''', (True, mac_address, username))
        cursor.close()
        conn.commit()
        conn.close()

    def remember_me_off(self, username):
        """
        Update the 'remember_me' and 'mac_address' fields in the 'users' table for a specific user.
        The 'remember_me' field is set to False and the 'mac_address' field is set to an empty string.
        Parameters:
            username (str): The username of the user to update.
        """
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''UPDATE users SET remember_me=(?), mac_address=(?) WHERE username=(?)''', (False, "", username))
        cursor.close()
        conn.commit()
        conn.close()

    def check_mac_address(self, mac_address):
        """
        Check if the given MAC address exists in the database.
        Parameters:
            mac_address: str - the MAC address to check
        return: bool - True if the MAC address exists, False otherwise
        """
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM users WHERE mac_address=(?)''', (mac_address,))
        result = cursor.fetchall() != []
        cursor.close()
        conn.close()
        return result # returns true or false

    def update_other_users_mac_address(self, mac_address):
        """
        Updates the mac address for other users in the database.
        If the given mac address is found in the database, it updates the 'remember_me' field for this user to False.

        Parameters:
            mac_address (str) : the new mac address to be updated
        """
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM users WHERE mac_address=(?)''', (mac_address,))
        result = cursor.fetchone()
        if result:
            cursor.execute('''UPDATE users SET mac_address=(?), remember_me=(?)''', ("", False))
            conn.commit()
        cursor.close()
        conn.close()

    def get_username_by_mac(self, mac_address):
        """
        Return the username associated with the provided MAC address from the database.
        Parameters:
            mac_address (str): The MAC address for which to retrieve the associated username.
        Returns:
            str: The username associated with the provided MAC address.
        """
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT username FROM users WHERE mac_address=(?)''', (mac_address,))
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return result

class ScoresDB:
    def __init__(self):
        """
        Initializes the class with default values for database, score_coefficient, and encryption.
        """
        self.database = 'scores.db'
        self.score_coefficient = 0.8 # The scoring coefficient | As much as it higher, the effect of the new score is lower and the effect of the mean is higher
        self.encryption = Encryption()

    def connect_to_db(self):
        conn = sqlite3.connect(self.database)
        return conn

    def create_table(self):
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scores (
                username TEXT, 
                game TEXT,
                lastScore INTEGER,
                mean INTEGER,
                FOREIGN KEY (username) REFERENCES users(username)
            )
        ''')
        conn.commit()
        cursor.close()
        conn.close()

    def insert_score(self, username, game, score, new_mean):
        # Working here
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        if self.checkUserExists(username):
            cursor.execute('''UPDATE scores SET lastScore=(?), mean=(?) WHERE username=(?) AND game=(?)''', (score, new_mean, username, game))
        else:
            cursor.execute('''INSERT INTO scores VALUES (?, ?, ?, ?)''', (username, game, score, new_mean))
        conn.commit()
        cursor.close()
        conn.close()

    def checkUserExists(self, username):
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM scores WHERE username=(?)''', (username,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return not result == []

    def getMean(self, username):
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT mean FROM scores WHERE username=(?) AND game=(?)''', (username, "sorting numbers"))
        mean = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        if mean:
            return mean
        return 0

    def get_last_score(self, username):
        self.create_table()
        conn = self.connect_to_db()
        cursor = conn.cursor()
        cursor.execute('''SELECT lastScore FROM scores WHERE username=(?) AND game=(?)''', (username, "sorting numbers"))
        lastScore = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        if lastScore:
            return lastScore
        return 0

class Message:

    def __init__(self):
        self.username = ''
        self.password = ''
        self.database = UsersDB()
    
    def decode_json(self, data):
        # gets data of bytes type
        # returns the data as a the list type
        try:
            decoded_data = data.decode()
            if decoded_data:
                return json.loads(decoded_data)
            else:
                # Handle the case when the decoded data is empty
                return None
        except json.decoder.JSONDecodeError as e:
            # Handle the invalid JSON case
            print(f"Error decoding JSON: {e}")
            return None
        
    def encode_json(self, data):
        # gets data of list type
        # returns the data as a bytes type
        try:
            json_data = json.dumps(data)
            return json_data.encode()
        except json.decoder.JSONDecodeError as e:
            # Handle the invalid JSON case
            print(f"Error decoding JSON: {e}")
            return None
        
class Sorting_Numbers:
    def __init__(self):
        self.numbers_to_sort = []
    
    def generate_numbers(self):
        numbers_to_sort = random.sample(range(1, 10), 5)
        random.shuffle(numbers_to_sort)
        self.numbers_to_sort = numbers_to_sort
        return numbers_to_sort

class Encryption:
    def __init__(self):
        # Initialize any necessary variables or objects here
        self.key = RSA.generate(1024)
        self.CHUNK_SIZE = 86
        self.public_key = self.key.publickey()
        self.private_key = self.key
        self.encryption_keys = {}
    
    def generate_symetric_key(self):
        # Implement code to generate encryption key
        return Fernet.generate_key()
    
    def import_public_key(self, pem_key):
        return RSA.import_key(pem_key)
    
    def encrypt_data(self, plaintext, symetric_key):
        cipher = Fernet(symetric_key)
        ciphertext = cipher.encrypt(plaintext)
        
        return ciphertext
    
    def decrypt_data(self, ciphertext, symmetric_key):
        cipher = Fernet(symmetric_key)
        plaintext = cipher.decrypt(ciphertext)

        return plaintext
    
    def decrypt_symmetric_key(self, ciphertext):
        cipher = PKCS1_OAEP.new(self.private_key)
        chunk_size = 128
        plaintext = b""
        for i in range(0, len(ciphertext), chunk_size): # Decrypt in chunks
            chunk = ciphertext[i:i + chunk_size]
            decrypted_chunk = cipher.decrypt(chunk)
            plaintext += decrypted_chunk

        return plaintext