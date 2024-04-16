import socket
import select
from server_utils import UsersDB, ScoresDB, Message, Sorting_Numbers, Encryption
from getmac import getmac
import json
import random

SERVER_IP = '10.100.102.12' # IP address of the server
SERVER_PORT = 12345 # Port to listen on

class Server:
    """
        Initializes the Server class with the specified host and port.
        - Creates a server socket using the provided host and port.
        - Initializes various data structures for user names, clients, chat players, and messages.
        - Loads associations from the 'associations.json' file.
        - Instantiates databases for users and scores.
        - Initializes lists for rlist, wlist, and xlist.
        """
    
    def __init__(self, host, port):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        self.message = Message()
        self.encryption = Encryption()

        self.clients = [self.server_socket]
        self.clients_names = {}
        self.not_sent_msg_clients = {}
        self.sent_clients = []
        
        self.curr_asso_index = -1
        self.waiting_for_next_round = 0
        self.wfc = []
        self.chat_players = {}
        self.chat_messages = {}
        self.chat_players_flags = 0
        self.used_words = []
        self.SCORE_COEFFINIENT = 0.8 # The scoring coefficient | As much as it higher, the effect of the new score is lower and the effect of the mean is higher


        with open('./Server/associations.json', 'r') as file:
            self.associations = json.load(file)

        self.database = UsersDB()
        self.scores = ScoresDB()
        self.sorting_numbers = Sorting_Numbers()
        self.messages = {}

        # Initialize rlist, wlist, and xlist
        self.rlist = []
        self.wlist = []
        self.xlist = []


    def start(self):
        """
        Start the server and continuously listen for incoming connections.
        Accept new connections, handle data from existing clients, and manage disconnections.
        """
        print(f"Server is listening on {self.server_socket.getsockname()}")

        while True:
            # Copy the clients list to rlist for monitoring read events
            self.rlist = list(self.clients)
            rlist, _, _ = select.select(self.rlist, self.wlist, self.xlist)

            for sock in rlist:  
                if sock == self.server_socket:
                    # New connection, accept it
                    client_socket, client_address = self.server_socket.accept()
                    self.clients.append(client_socket)
                    print(f"New connection from {client_address}")

                    # GETTING THE SYMMETRIC KEY FROM THE CLIENT
                    serialized_public_key = self.encryption.public_key.export_key()
                    client_socket.sendall(serialized_public_key)
                    encrypted_symetric_key = client_socket.recv(1024)
                    self.encryption.encryption_keys[client_socket] = self.encryption.decrypt_symmetric_key(encrypted_symetric_key)

                    mac_address = getmac.get_mac_address(ip=client_address[0]) # gets client's mac address    
                    self.clients_names[client_socket] = [mac_address, ""]
                    if self.database.check_mac_address(mac_address): # checks if mac address saved in database
                        username = self.database.get_username_by_mac(mac_address) # gets username from database by the mac address
                        self.clients_names[client_socket][1] = username # saves the username in the clients_names dictionary
                        client_socket.send(self.message.encode_json(["remember me", username])) # sends a message and the username to the client
                else:
                    # Handle data from an existing client
                    try:
                        encoded_data = sock.recv(1024) # receives data from client
                        data = list(self.message.decode_json(encoded_data)) # decodes data
                        self.messages[sock] = data
                        result_msg = self.handle_messages()
                        if result_msg is not None:
                            if (result_msg[0] == "login" or result_msg[0] == "signup") and result_msg[1] == "success":
                                self.clients_names[sock][1] = result_msg[2]
                            result_json_msg = self.message.encode_json(result_msg)
                            sock.send(result_json_msg)

                    except:
                        # Client disconnected
                        username = self.clients_names[sock][1]
                        if username in self.chat_players: # if the client is in the chat players list then remove it 
                            self.chat_players.pop(username)
                            if len(self.wfc) != 0:
                                joining_player_socket = self.get_sock_by_username(self.wfc[0])
                                self.chat_players[joining_player_socket] = [self.wfc[0], 0]
                                self.clients_names[self.wfc[0]].send(self.message.encode_json(["game", "chat", "joining"]))
                        self.clients_names.pop(sock)
                        self.clients.remove(sock)
                        print("Server: Client has been disconnected")
                    

    def handle_messages(self):
        """
            A function to handle different types of messages received, such as login, signup, database queries, and game interactions.
            Manages login attempts, user registration, database checks, game actions like sorting numbers and chat functionality.
            The function processes the messages and returns appropriate responses accordingly.
        """
        for sock in self.messages:
            msg = self.messages[sock]
            if type(msg) is list:
                if msg[0] == "login":
                    # handle login requests
                    return self.handle_login(msg[1], msg[2], msg[3], sock) # username, password, remember_me, sock
                    
                if msg[0] == "signup":
                    # handle signup requests
                    return self.handle_signup(msg[1], msg[2], msg[3], sock) # username, password, remember_me, sock

                if msg[0] == "database":
                    # handle database queries
                    return self.handle_database_queries(msg, sock)
                
                if msg[0] == "game":
                    # handle game interactions
                    if msg[1] == "sorting numbers":
                        # handle sorting numbers game
                        return self.handle_sorting_numbers_game(msg, sock)
                    
                    if msg[1] == "chat":
                        # handle associations game
                        return self.handle_associations_game(msg, sock)

    def handle_login(self, username, password, remember_me, sock):
        if not self.database.check_user_registered(username):
            # the username is not exists
            self.messages.pop(sock)
            return ["login", "error", "no user exists"]
        elif self.database.try_login(username, password, self.encryption.encryption_keys[sock]):
            # 
            # handle login success
            if not bool(self.database.check_remember_me(username)) and remember_me:
                mac_address = self.clients_names[sock][0]
                self.database.update_other_users_mac_address(mac_address)
                self.database.remember_me_on(mac_address, username)
                
            encryption_key = self.encryption.encryption_keys[sock]
            self.messages.pop(sock)
            return ["login", "success", username] # msg[1] -> username
        else:
            # handle login failure
            self.messages.pop(sock)
            return ["login", "error", "incorrect password"]

    def handle_signup(self, username, encrypted_password, remember_me, sock):
        if not self.database.check_user_registered(username):
            # the username is not exists
            mac_address = self.clients_names[sock][0]
            decrypted_password = self.encryption.decrypt_data(eval(encrypted_password), self.encryption.encryption_keys[sock])
            if remember_me:
                self.database.update_other_users_mac_address(mac_address)
                self.database.insert_user(username, decrypted_password, remember_me, mac_address)
            else:
                self.database.insert_user(username, decrypted_password, remember_me, "")
            print("new user successfully registered")
            self.messages.pop(sock)
            return ["signup", "success", username] # [2] -> username
        else:
            # the username is already exists
            print("This username is already exists")
            self.messages.pop(sock)
            return ["signup", "error"]

    def handle_database_queries(self, msg, sock):
        if msg[1] == "check remember me status":
            # check if the user has remember me on or off
            self.messages.pop(sock)
            return self.check_remember_me(msg[2])
        
        elif msg[1] == "change remember me":
            self.change_remember_me(self, msg[2], msg[3], sock)
            self.messages.pop(sock)
            return ["changed remember me"]
        
        elif msg[1] == "get last score mean":
            # get last score and mean (sort numbers game)
            return self.get_last_score_mean(msg[2], sock)
        
    def handle_sorting_numbers_game(self, msg, sock):
        if msg[2] == "start":
            # generate random numbers and send them to the client
            numbers = self.sorting_numbers.generate_numbers()
            self.messages.pop(sock)
            return ["game", "sorting numbers", numbers]
        
        elif msg[2] == "check sorted numbers":
            # check if the sorted numbers are correct
            if int(msg[3]) == int(''.join(map(str, sorted(self.sorting_numbers.numbers_to_sort)))):
                # if correct, send success message
                self.messages.pop(sock)
                return ["game", "sorting numbers", "success"]
            self.messages.pop(sock)
            # if not correct, send fail message
            return ["game", "sorting numbers", "fail"]

        elif msg[2] == "set score":
            # set the score in the database (scores.db) and send it to the client
            time = msg[4]
            username = msg[3]
            score = int(((300-time)/30)**2)
            if self.scores.checkUserExists(username):
                last_mean = self.scores.getMean(username)
                new_mean = int((last_mean*self.SCORE_COEFFINIENT) + (score*(1-self.SCORE_COEFFINIENT)))
                encrypted_score = self.encryption.encrypt_data(str(score).encode(), self.encryption.encryption_keys[sock])
                self.scores.insert_score(username, "sorting numbers", str(score), str(new_mean))
            else:
                new_mean = score
                encrypted_score = self.encryption.encrypt_data(str(score).encode(), self.encryption.encryption_keys[sock])
                self.scores.insert_score(username, "sorting numbers", str(score), str(score))
            self.messages.pop(sock)
            return ["game", "sorting numbers", "successfully set score", str(encrypted_score)]
            
    def handle_associations_game(self, msg, sock):
        # handle association game
        if msg[2] == "join":
            # join the chat if there is space (max: 5 players)
            if len(self.chat_players) == 5:
                # if there is no space, send error message
                self.wfc.append(msg[3])
                self.messages.pop(sock)
                return ["game", "chat", "full chat"]
            else:
                # if there is space, join the chat
                self.chat_players[sock] = [msg[3], 0] # updating player list that currently in the chat
                self.wfc = []
                self.chat_players_flags = len(self.chat_players)
                self.messages.pop(sock)
                if self.chat_players_flags == 1: # checks if this user is the only user that is in the chat
                    index = random.randint(0, len(self.associations.keys())-1) # picks an index between 0 to num of the keys in the associations.json file
                    while index == self.curr_asso_index:
                        # if the chosen index is the last index, it will choose another index untill it will be a new index
                        index = random.randint(0, len(self.associations.keys())-1) # picks an index between 0 to num of the keys in the associations.json file
                    self.curr_asso_index = index
                    # send joining message
                    return ["game", "chat", "joining", list(self.associations.keys())[index]]
                self.waiting_for_next_round += 1
                # if there is space and the user is not the only user, send joining message of waiting for next round
                return ["game", "chat", "waiting for round"]
        
        elif msg[2] == "leave":
            # leave the chat
            if len(self.wfc) != 0:
                # if there are waiting clients, send the first one to join the chat
                self.chat_players[sock] = [self.wfc[0], 0]
                for sock2 in self.clients_names:
                    if self.clients_names[sock2][1] == self.wfc[0]:
                        sock2.send(self.message.encode_json(["game", "chat", "joining"]))
            score = self.chat_players[sock][1]
            self.chat_players.pop(sock)
            self.chat_players_flags = len(self.chat_players)
            if sock in self.not_sent_msg_clients:
                self.not_sent_msg_clients.pop(sock)
            self.messages.pop(sock)
            return ["game", "chat", "kicking client", score]
        
        elif msg[2] == "sending temp message":
            # send a temporary message in order to pass the sock.recv() function (which is blocking) in the server.py
            self.messages.pop(sock)
            return ["game", "chat", "temp message"]

        elif msg[2] == "cancel":
            # cancel the request to join the chat
            if msg[3] in self.wfc:
                self.wfc.remove(msg[3]) # removes the client from the waiting list
            if sock in self.chat_players:
                self.chat_players.pop(sock)
                self.chat_players_flags = len(self.chat_players)
            self.messages.pop(sock)
            return ["game", "chat", "cancel"]

        elif msg[2] == "send message":
            # send message in the chat
            if sock not in self.sent_clients:
                self.sent_clients.append(sock)
            
            if msg[4] in self.used_words:
                # if the message is already used, send error message
                self.messages.pop(sock)
                return ["game", "chat", "already used"]
            if msg[4].lower() in self.associations[list(self.associations.keys())[self.curr_asso_index]]:
                # if the message is correct, send success message
                self.chat_messages[sock] = str(msg[3] + ": " + msg[4])
                self.used_words.append(msg[4])
                self.chat_players[sock][1] += 1
                self.broadcast_message()
                return ["game", "chat", "sent"]
            # if the message is not correct, send error message
            self.messages.pop(sock)
            return ["game", "chat", "nope"]

        elif msg[2] == "change subject":
            # change the subject in the chat every 60 seconds
            if sock not in self.sent_clients:
                if sock not in self.not_sent_msg_clients.keys():
                    self.not_sent_msg_clients[sock] = 1
                else:
                    self.not_sent_msg_clients[sock] = 2
            
            elif sock in self.not_sent_msg_clients:
                self.not_sent_msg_clients.pop(sock)
            
            if sock in self.not_sent_msg_clients and self.not_sent_msg_clients[sock] == 2:
                # if the client did not send a message in 2 rounds, kick the client
                if len(self.wfc) != 0:
                    # if there are waiting clients, send the first one to join the chat
                    self.chat_players[sock] = [self.wfc[0], 0]
                    for sock2 in self.clients_names:
                        if self.clients_names[sock2][1] == self.wfc[0]:
                            sock2.send(self.message.encode_json(["game", "chat", "joining"]))                                
                score = self.chat_players[sock][1]
                self.chat_players.pop(sock)
                self.chat_players_flags = len(self.chat_players)
                self.not_sent_msg_clients.pop(sock)
                self.messages.pop(sock)
                return ["game", "chat", "kicking client", score]
            
            self.sent_clients = []
            # waiting for all the players that are in the chat and then changing the subject
            self.chat_players_flags -= self.waiting_for_next_round
            if self.chat_players_flags != 1:
                self.chat_players_flags -= 1
                self.messages.pop(sock)
                return None
            else:
                self.chat_players_flags = len(self.chat_players)
                index = random.randint(0, len(self.associations.keys())-1) # picks an index between 0 to num of the keys in the associations.json file
                while index == self.curr_asso_index:
                    # if the chosen index is the last index, it will choose another index untill it will be a new index
                    index = random.randint(0, len(self.associations.keys())-1) # picks an index between 0 to num of the keys in the associations.json file
                self.curr_asso_index = index
                for s_player in self.chat_players.keys():
                    if s_player != sock: # sending the message to each player in the game except the player who sent the message
                        s_player.send(self.message.encode_json(["game", "chat", "new round", list(self.associations.keys())[index]]))
                self.messages.pop(sock)
                self.waiting_for_next_round = 0
                self.used_words = []
                return ["game", "chat", "new round", list(self.associations.keys())[index]]

    def check_remember_me(self, username):
        return [bool(self.database.check_remember_me(username))]

    def change_remember_me(self, remember_me_status, username, sock):
        # change remember me status
        if remember_me_status:
            # set remember me on
            self.database.remember_me_on(self.clients_names[sock][0], username)
        else:
            # set remember me off
            self.database.remember_me_off(username)

    def get_last_score_mean(self, username, sock):
        encryption_key = self.encryption.encryption_keys[sock]
        if self.scores.checkUserExists(username):
            # if the user exists
            score = self.scores.get_last_score(username)
            encrypted_score = self.encryption.encrypt_data(str(score).encode(), encryption_key)
            mean = self.scores.getMean(username)
            encrypted_mean = self.encryption.encrypt_data(str(mean).encode(), encryption_key)
            self.messages.pop(sock)
            return [str(encrypted_score), str(encrypted_mean)]
        # if the user doesn't exist, send encrypted [0, 0]
        encrypted_score = self.encryption.encrypt_data(str(0).encode(), encryption_key)
        self.messages.pop(sock)
        return [str(encrypted_score), str(encrypted_score)]

    def broadcast_message(self):
        '''
        The function executes when a player sends a message in the chat
        The function sends the message to each player in the chat (if he corrects) except the player who sent the message
        '''
        messages_to_remove = []
        for sender_socket in self.chat_messages:            
            for chat_member_socket in self.chat_players:
                if sender_socket is chat_member_socket: # not sending the message to the player who sent the message
                    pass
                else:
                    chat_member_socket.send(self.message.encode_json(self.chat_messages[sender_socket]))
            messages_to_remove.append(sender_socket)
        
        for sender_socket in messages_to_remove:
            self.chat_messages.pop(sender_socket, None)

    def get_sock_by_username(self, username):
        for socket in self.clients_names:
            if self.clients_names[socket][1] == username:
                return socket

if __name__ == "__main__":
    server = Server(SERVER_IP, SERVER_PORT)
    server.start()
    