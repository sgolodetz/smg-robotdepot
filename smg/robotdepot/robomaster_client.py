import socket
import struct
import threading
import time

from typing import Tuple


class RobomasterClient:
    """A client that can be used to communicate with a server running on a DJI Robomaster S1."""

    # CONSTRUCTOR

    def __init__(self, endpoint: Tuple[str, int] = ("192.168.2.1", 7860), *, timeout: int = 10,
                 print_commands: bool = True):
        """
        Construct a Robomaster client.

        :param endpoint:        The server host and port, e.g. ("192.168.2.1", 7860).
        :param timeout:         The socket timeout to use (in seconds).
        :param print_commands:  Whether or not to print commands that are sent.
        """
        self.__alive: bool = False
        self.__print_commands: bool = print_commands
        self.__should_terminate: threading.Event = threading.Event()

        self.__chassis_fwd: float = 0
        self.__gimbal_yaw: float = 0

        # Try to connect to the server.
        try:
            self.__sock: socket.SocketType = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.__sock.connect(endpoint)
            self.__sock.settimeout(timeout)
            self.__alive = True
        except ConnectionRefusedError:
            # If we can't connect to the server, raise an exception.
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

    def set_chassis_fwd(self, rate: float) -> None:
        """
        Tell the robot's chassis to move forward at the specified rate.

        .. note::
            This can also be used to move backwards (by specifying a negative rate).

        :param rate:    The rate at which the robot's chassis should move forward (in [-1,1]).
        """
        self.__chassis_fwd = RobomasterClient.__rate_to_control_value(rate)

    def set_gimbal_yaw(self, rate: float) -> None:
        """
        Tell the robot's gimbal to turn at the specified rate.

        .. note::
            If the robot's chassis is set to follow its gimbal, this will cause the chassis to turn as well.

        :param rate:    The rate at which the gimbal should turn (in [-1,1]).
        """
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
            cmd: str = f"control {self.__chassis_fwd} {self.__gimbal_yaw}"

            # Send the command.
            self.__send_command(cmd)

    def __send_command(self, cmd: str) -> None:
        """
        Send the specified command to the robot.

        :param cmd: The command to send.
        """
        with self.__cmd_lock:
            # Send the command, prepended by its length.
            msg: bytes = cmd.encode("utf-8")
            self.__sock.send(struct.pack("<i", len(msg)) + msg)

            # Print the command that was sent, if desired.
            if self.__print_commands:
                print(f"Sent Command: {cmd}")

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
