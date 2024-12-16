import multiprocessing
import mimetypes
import os
import pathlib
from datetime import datetime
from functools import partial
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import socket
from dotenv import load_dotenv
import logging
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(level=getattr(logging, log_level, logging.DEBUG),
                    format='%(asctime)s - %(levelname)s - %(message)s')


class SocketWriter:
    def __init__(self, socket_ip, socket_port):
        self.socket_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket_server = socket_ip, socket_port

    def close(self):
        self.socket_client.close()

    def write(self, data):
        self.socket_client.sendto(data, self.socket_server)
        logging.debug(f'Send data: {data.decode()} to socket: {self.socket_server}')

class Storage:
    def __init__(self, host, port, user, password, db_name, collection_name):
        connection_string = f"mongodb://{user}:{password}@{host}:{port}/"
        self.client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        logging.debug(f"Connected to MongoDB, Database: {db_name}, collection: {collection_name}")

    def insert_one(self, data):
        self.collection.insert_one(data)

    def close(self):
        self.client.close()


class HttpHandler(BaseHTTPRequestHandler):
    def __init__(self, socket_writer: SocketWriter, *args, **kwargs):
        self.socket_writer = socket_writer

        super().__init__(*args, **kwargs)

    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == '/':
            self.send_html_file('index.html')
        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file('error.html', 404)

    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        self.socket_writer.write(data)
        self.send_response(302)
        self.send_header('Location', '/message.html')
        self.end_headers()

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        with open(filename, 'rb') as fd:
            self.wfile.write(fd.read())

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", 'text/plain')
        self.end_headers()
        with open(f'.{self.path}', 'rb') as file:
            self.wfile.write(file.read())

class UDPServer:
    def __init__(self, ip, port, storage: Storage):
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.ip, self.port))
        self.storage = storage

    def run(self):
        while True:
            data, address = self.sock.recvfrom(1024)
            parsed_data = dict(urllib.parse.parse_qsl(urllib.parse.unquote_plus(data.decode())))
            parsed_data["date"] = datetime.now()
            logging.debug(f'Received data: {data.decode()} from: {address}')

            try:
                self.storage.insert_one(parsed_data)
            except Exception as e:
                logging.error(f'Failed write data into storage, data: {parsed_data}, error: {e}')
            

    def close(self):
        self.sock.close()

def run_udp_server(ip, port):
    storage = Storage(
        host=os.environ.get('MONGO_HOST', 'localhost'),
        port=int(os.environ.get('MONGO_PORT', 27017)),
        user=os.environ.get('MONGO_USER', 'user'),
        password=os.environ.get('MONGO_PASS', 'password'),
        db_name=os.environ.get('MONGO_DBNAME', 'test_db'),
        collection_name=os.environ.get('MONGO_COLLECTION', 'test_collection')
    )

    udp_server = UDPServer(ip, port, storage)

    try:
        logging.debug(f"UDP server started on ip: {ip}, port: {port}")
        udp_server.run()

    except KeyboardInterrupt:
        logging.debug('Destroy UDP server')
    finally:
        udp_server.close()
        storage.close()


def run_http_server(port, socket_ip, socket_port, ):
    soket_writer = SocketWriter(socket_ip, socket_port)

    server_address = ('', port)
    handler = partial(HttpHandler, soket_writer)
    http = HTTPServer(server_address, handler)

    try:
        logging.debug(f'Http server started on port: {port}')
        http.serve_forever()
    except KeyboardInterrupt:
        logging.debug('Destroy HTTP server')
    finally:
        http.server_close()
        soket_writer.close()


if __name__ == '__main__':
    udp_ip = os.environ.get('UDP_IP', '127.0.0.1')
    udp_port = int(os.environ.get('UDP_PORT', 5000))
    http_port = int(os.environ.get('HTTP_PORT', 3000))

    http_process = multiprocessing.Process(target=run_http_server, args=(http_port, udp_ip, udp_port,))
    udp_process = multiprocessing.Process(target=run_udp_server, args=(udp_ip, udp_port,))

    http_process.start()
    udp_process.start()
    http_process.join()
    udp_process.join()
