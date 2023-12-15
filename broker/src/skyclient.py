import socket
import os
import time

COMMAND = "INVOKE_FUNCTION"
function = "func13411251"

def send_command(client_socket, command):
    # Send a command to the server
    client_socket.sendall(command.encode())
    time.sleep(0.2)

def send_file(client_socket, file_path, directory_label):
    # Get the size of the file
    file_size = os.path.getsize(file_path)

    # Prepare file information: name, size, and originating directory
    file_info = f"{os.path.basename(file_path)}|{file_size}|{directory_label}\n"

    # Send file information
    client_socket.sendall(file_info.encode())

    # Send the file in chunks
    with open(file_path, 'rb') as file:
        while True:
            bytes_read = file.read(1024)
            if not bytes_read:
                break
            client_socket.sendall(bytes_read)

    time.sleep(0.2)

def send_files_from_directory(client_socket, directory, directory_label):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            send_file(client_socket, file_path, directory_label)

def main():
    host = '127.0.0.1'  # Replace with the server's IP address or hostname
    port = 12345  # The port should match the server

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        client_socket.connect((host, port))

        send_command(client_socket, COMMAND)

        time.sleep(0.1)

        if COMMAND == "CREATE_FUNCTION":
            # Send AWS files
            send_files_from_directory(client_socket, 'aws_send', 'aws_send')

            # Send Google Cloud files
            send_files_from_directory(client_socket, 'gcloud_send', 'gcloud_send')

        elif COMMAND == "INVOKE_FUNCTION":
            client_socket.sendall(function.encode())
            time.sleep(0.2)
            send_file(client_socket, './dog2.jpeg', './')

if __name__ == "__main__":
    main()
