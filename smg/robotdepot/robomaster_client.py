import socket
import struct
import threading
import time

from typing import Tuple


class RobomasterClient:
    """TODO"""

    # CONSTRUCTOR

    def __init__(self, endpoint: Tuple[str, int] = ("192.168.2.1", 7860), *, timeout: int = 10):
        self.__alive: bool = False
        self.__should_terminate: threading.Event = threading.Event()

        self.__gimbal_yaw: float = 0

        # Connect to the server.
        try:
            self.__sock: socket.SocketType = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.connect(endpoint)
            self.__sock.settimeout(timeout)
            self.__alive = True
        except ConnectionRefusedError:
            raise RuntimeError("Error: Could not connect to the server")

        # Set up the locks.
        self.__cmd_lock: threading.Lock = threading.Lock()

        # Start the threads.
        self.__heartbeat_thread: threading.Thread = threading.Thread(target=self.__process_heartbeats)
        self.__heartbeat_thread.start()

    # DESTRUCTOR

    def __del__(self):
        """Destroy the client."""
        self.terminate()

    # SPECIAL METHODS

    def __enter__(self):
        """No-op (needed to allow the client's lifetime to be managed by a with statement)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Destroy the client at the end of the with statement that's used to manage its lifetime."""
        self.terminate()

    # PUBLIC METHODS

    def set_gimbal_yaw(self, rate: float) -> None:
        self.__gimbal_yaw = RobomasterClient.__rate_to_control_value(rate)

    def terminate(self) -> None:
        """Tell the client to terminate."""
        if self.__alive:
            self.__should_terminate.set()
            self.__heartbeat_thread.join()
            self.__sock.shutdown(socket.SHUT_RDWR)
            self.__sock.close()
            self.__alive = False

    # PRIVATE METHODS

    def __process_heartbeats(self) -> None:
        """Send regular movement control messages to the robot."""
        while not self.__should_terminate.is_set():
            # Sleep for 100 milliseconds.
            time.sleep(0.1)

            # Construct the movement control command to send to the robot.
            cmd: str = f"control {self.__gimbal_yaw}"

            # Send the command.
            self.__send_command(cmd)

    def __send_command(self, cmd: str) -> None:
        print(cmd)
        with self.__cmd_lock:
            msg: bytes = cmd.encode("utf-8")
            self.__sock.send(struct.pack("<i", len(msg)) + msg)

    # PRIVATE STATIC METHODS

    @staticmethod
    def __rate_to_control_value(rate: float) -> int:
        """
        Convert a floating-point rate to an integer control value in [-100,100].

        :param rate:    The rate.
        :return:        The control value.
        """
        if rate < -1.0:
            rate = -1.0
        if rate > 1.0:
            rate = 1.0
        return int(100 * rate)
