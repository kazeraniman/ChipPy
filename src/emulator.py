import logging
import sys
import random
import pygame
import threading
import numpy as np

from typing import List, Tuple, Optional

from pathlib import Path

# Set up the logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s]:  %(message)s", stream=sys.stdout)
logger.disabled = "pydevd" not in sys.modules

# Constants
UPPER_CHAR_MASK = 240
LOWER_CHAR_MASK = 15
BYTE_MASK = 255
GAME_START_ADDRESS = 512
RETURN_FROM_SUBROUTINE_OPCODE = bytes.fromhex("00EE")
SCREEN_WIDTH = 64
SCREEN_HEIGHT = 32
OPCODE_DELAY = 1/60
SOUND_FREQUENCY = 44100
SOUND_BUFFER = 4096
TONE_HZ = 550

# Initialize the random number generator
random.seed()

# Initialize PyGame
pygame.mixer.init(SOUND_FREQUENCY, -16, 1, 4096)
pygame.init()


class Emulator:
    """
    The class which hold all the functionality of the emulator.
    """
    def __init__(self):
        """
        Constructor.
        """
        self.ram = bytearray(4096)
        self.registers = bytearray(16)
        self.register_i = 0
        self.delay = 0
        self.sound = 0
        self.program_counter = GAME_START_ADDRESS
        self.stack: List[int] = []
        self.screen = None
        self.pixels: List[List[bool]] = []
        for i in range(SCREEN_HEIGHT):
            self.pixels.append([False] * SCREEN_WIDTH)

        self.opcode_timer: Optional[threading.Timer] = None
        self.delay_timer: Optional[threading.Timer] = None
        self.sound_timer: Optional[threading.Timer] = None

        # Sound is weird; borrowing some of this chunk from here, I claim no credit for it: http://shallowsky.com/blog/programming/python-play-chords.html
        length = SOUND_FREQUENCY / TONE_HZ
        omega = np.pi * 2 / length
        x_values = np.arange(int(length)) * omega
        one_cycle = SOUND_BUFFER * np.sin(x_values)
        sound_wave = np.resize(one_cycle, (SOUND_FREQUENCY,)).astype(np.int16)
        self.sound_player = pygame.sndarray.make_sound(sound_wave)

    def __del__(self):
        """
        Destructor.
        """
        self.kill_all_timers()

    def load_game(self, path: Path) -> None:
        """
        Load the game found at the given path into memory.
        :param path: The path to the game.
        """
        if not path:
            logger.error("No path provided for a game to load!")
            return

        if not path.exists():
            logger.error(f"Game could not be loaded as the path does not exist!  Path: {path}.")
            return

        if path.suffix != ".chip8":
            logger.error("Game does not appear to be a CHIP-8 game as the '.chip8' file type was not found in the file name.  Path: {path}.")
            return

        logger.debug(f"Loading game at path {path}.")
        with path.open("rb") as file:
            game = file.read()
            for index, value in enumerate(game):
                self.ram[512 + index] = value

    def print_ram(self) -> None:
        """
        Dump the full memory of the emulator.
        """
        for byte in self.ram:
            print(hex(byte))

    def game_loop(self) -> None:
        """
        Temporary game loop which loads a game, sets up a screen, and then starts the fetch-execute loop.
        """
        self.load_game(Path("../games/INVADERS.chip8"))
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.fetch_and_run_opcode()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit(0)

    # region Timers
    def decrement_delay_timer(self) -> None:
        """
        Decrement the value of the delay timer, restarting it if the value is still above 0.
        """
        self.toggle_delay_timer(False)
        self.delay -= 1
        logger.debug(f"Delay timer decremented, new value is {self.delay}.")
        if self.delay <= 0:
            self.delay = 0
        else:
            self.toggle_delay_timer(True)
            logger.debug(f"Starting delay timer.")

    def decrement_sound_timer(self) -> None:
        """
        Decrement the value of the sound timer, restarting it if the value is still above 0, stopping the sound otherwise.
        """
        self.toggle_sound_timer(False)
        self.sound -= 1
        logger.debug(f"Sound timer decremented, new value is {self.sound}.")
        if self.sound <= 0:
            self.sound = 0
            self.sound_player.stop()
            logger.debug(f"Stopping sound.")
        else:
            self.toggle_sound_timer(True)
            logger.debug(f"Starting sound timer.")

    def kill_all_timers(self) -> None:
        """
        Stop all timers.
        """
        self.toggle_opcode_timer(False)
        self.toggle_delay_timer(False)
        self.toggle_sound_timer(False)

    def toggle_opcode_timer(self, status: bool) -> None:
        """
        Start / stop the opcode timer.
        :param status: True if the timer should be started, false otherwise.
        """
        if self.opcode_timer:
            self.opcode_timer.cancel()

        if status:
            self.opcode_timer = threading.Timer(OPCODE_DELAY, self.fetch_and_run_opcode)
            self.opcode_timer.daemon = True
            self.opcode_timer.start()

    def toggle_delay_timer(self, status: bool) -> None:
        """
        Start / stop the delay timer.
        :param status: True if the timer should be started, false otherwise.
        """
        if self.delay_timer:
            self.delay_timer.cancel()

        if status:
            self.delay_timer = threading.Timer(OPCODE_DELAY, self.decrement_delay_timer)
            self.delay_timer.daemon = True
            self.delay_timer.start()

    def toggle_sound_timer(self, status: bool) -> None:
        """
        Start / stop the sound timer.
        :param status: True if the timer should be started, false otherwise.
        """
        if self.sound_timer:
            self.sound_timer.cancel()

        if status:
            self.sound_timer = threading.Timer(OPCODE_DELAY, self.decrement_sound_timer)
            self.sound_timer.daemon = True
            self.sound_timer.start()
    # endregion

    # region Helpers
    @staticmethod
    def get_upper_char(byte: int) -> int:
        """
        Get the upper character (first 4 bits) of the given byte.
        :param byte: The byte from which to extract the character.
        :return: The upper character.
        """
        return (byte & UPPER_CHAR_MASK) >> 4

    @staticmethod
    def get_lower_char(byte: int) -> int:
        """
        Get the lower character (last 4 bits) of the given byte.
        :param byte: The byte from which to extract the character.
        :return: The lower character.
        """
        return byte & LOWER_CHAR_MASK

    @staticmethod
    def bounded_subtract(minuend: int, subtrahend: int) -> Tuple[int, int]:
        """
        Subtract the subtrahend from the minuend, bounded by the confines of a byte.
        :param minuend: The integer from which to subtract.
        :param subtrahend: The integer to subtract.
        :return: The result of the subtraction and the not borrow (1 if there was no borrow, 0 otherwise).
        """
        difference_of_registers = minuend - subtrahend
        result = difference_of_registers % 256
        not_borrow = 1 if difference_of_registers >= 0 else 0
        return result, not_borrow
    # endregion

    # region Opcodes
    def fetch_and_run_opcode(self) -> None:
        """
        Fetches the current instruction and executes it.
        """
        opcode = self.ram[self.program_counter:self.program_counter + 2]
        self.run_opcode(opcode)
        self.toggle_opcode_timer(True)

    def run_opcode(self, opcode: bytes) -> None:
        """
        Route the provided opcode to the correct method to execute it.  Increment the program counter to the next instruction.
        :param opcode: The opcode to execute.
        """
        self.program_counter += 2
        first_char = self.get_upper_char(opcode[0])
        last_char = self.get_lower_char(opcode[1])

        if opcode == RETURN_FROM_SUBROUTINE_OPCODE:
            self.opcode_return_from_subroutine(opcode)
        elif first_char == 1:
            self.opcode_goto(opcode)
        elif first_char == 2:
            self.opcode_call_subroutine(opcode)
        elif first_char == 3:
            self.opcode_if_equal(opcode)
        elif first_char == 4:
            self.opcode_if_not_equal(opcode)
        elif first_char == 5 and last_char == 0:
            self.opcode_if_register_equal(opcode)
        elif first_char == 6:
            self.opcode_set_register_value(opcode)
        elif first_char == 7:
            self.opcode_add_value(opcode)
        elif first_char == 8 and last_char == 0:
            self.opcode_set_register_value_other_register(opcode)
        elif first_char == 8 and last_char == 1:
            self.opcode_set_register_bitwise_or(opcode)
        elif first_char == 8 and last_char == 2:
            self.opcode_set_register_bitwise_and(opcode)
        elif first_char == 8 and last_char == 3:
            self.opcode_set_register_bitwise_xor(opcode)
        elif first_char == 8 and last_char == 4:
            self.opcode_add_other_register(opcode)
        elif first_char == 8 and last_char == 5:
            self.opcode_subtract_from_first_register(opcode)
        elif first_char == 8 and last_char == 6:
            self.opcode_bit_shift_right(opcode)
        elif first_char == 8 and last_char == 7:
            self.opcode_subtract_from_second_register(opcode)
        elif first_char == 8 and last_char == 14:
            self.opcode_bit_shift_left(opcode)
        elif first_char == 9 and last_char == 0:
            self.opcode_if_register_not_equal(opcode)
        elif first_char == 10:
            self.opcode_set_register_i(opcode)
        elif first_char == 11:
            self.opcode_goto_addition(opcode)
        elif first_char == 12:
            self.opcode_random_bitwise_and(opcode)
        elif first_char == 15 and opcode[1] == 7:
            self.opcode_get_delay_timer(opcode)
        elif first_char == 15 and opcode[1] == 21:
            self.opcode_set_delay_timer(opcode)
        elif first_char == 15 and opcode[1] == 24:
            self.opcode_set_sound_timer(opcode)
        else:
            logger.error(f"Unimplemented / Invalid Opcode: {opcode.hex()}.")

    def opcode_return_from_subroutine(self, opcode: bytes) -> None:
        """
        Return from the current subroutine.
        :param opcode: The opcode to execute.
        """
        if len(self.stack) == 0:
            logger.error("Tried to return from a subroutine when the stack is empty.  Ignoring.")
            return

        self.program_counter = self.stack.pop()
        logger.debug(f"Execute Opcode {opcode.hex()}: Return from subroutine, continue at {hex(self.program_counter)}.")

    def opcode_goto(self, opcode: bytes) -> None:
        """
        Jump to the provided address.
        :param opcode: The opcode to execute.
        """
        address = (self.get_lower_char(opcode[0]) << 8) + opcode[1]
        self.program_counter = address
        logger.debug(f"Execute Opcode {opcode.hex()}: Jump to address {hex(address)}.")

    def opcode_call_subroutine(self, opcode: bytes) -> None:
        """
        Call the subroutine at the given address.
        :param opcode: The opcode to execute.
        """
        address = (self.get_lower_char(opcode[0]) << 8) + opcode[1]
        self.stack.append(self.program_counter)
        self.program_counter = address
        logger.debug(f"Execute Opcode {opcode.hex()}: Call subroutine at address {hex(address)}.")

    def opcode_if_equal(self, opcode: bytes) -> None:
        """
        Skip the next instruction if the value of the provided register is equal to the provided value.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        logger.debug(f"Execute Opcode {opcode.hex()}: Skip next instruction if register {register}'s value ({register_value}) is {opcode[1]}.")
        if register_value == opcode[1]:
            self.program_counter += 2
            logger.debug("Instruction skipped.")
        else:
            logger.debug("Instruction not skipped.")

    def opcode_if_not_equal(self, opcode: bytes) -> None:
        """
        Skip the next instruction if the value of the provided register is not equal to the provided value.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        logger.debug(f"Execute Opcode {opcode.hex()}: Skip next instruction if register {register}'s value ({register_value}) is not {opcode[1]}.")
        if register_value != opcode[1]:
            self.program_counter += 2
            logger.debug("Instruction skipped.")
        else:
            logger.debug("Instruction not skipped.")

    def opcode_if_register_equal(self, opcode: bytes) -> None:
        """
        Skip the next instruction if the value of the first provided register is equal to the value of the second provided register.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        logger.debug(f"Execute Opcode {opcode.hex()}: Skip next instruction if register {first_register}'s value ({first_register_value}) is equal to register {second_register}'s value ({second_register_value}).")
        if first_register_value == second_register_value:
            self.program_counter += 2
            logger.debug("Instruction skipped.")
        else:
            logger.debug("Instruction not skipped.")

    def opcode_set_register_value(self, opcode: bytes) -> None:
        """
        Set the value of the provided register to the provided value.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        self.registers[register] = opcode[1]
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {register} to {opcode[1]}.")

    def opcode_add_value(self, opcode: bytes) -> None:
        """
        Adds the provided value to the value of the provided register.  The carry flag (register 15) is not set.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        self.registers[register] = (self.registers[register] + opcode[1]) % 256
        logger.debug(f"Execute Opcode {opcode.hex()}: Add {opcode[1]} to the value of register {register}.")

    def opcode_set_register_value_other_register(self, opcode: bytes) -> None:
        """
        Set the value of the first provided register to the value of the second provided register.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        second_register_value = self.registers[second_register]
        self.registers[first_register] = second_register_value
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {first_register} to the value of register {second_register}'s value ({second_register_value}).")

    def opcode_set_register_bitwise_or(self, opcode: bytes) -> None:
        """
        Sets the value of the first provided register to the bitwise or of itself and the value of the second provided register.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        result = first_register_value | second_register_value
        self.registers[first_register] = result
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {first_register} to the bitwise or of itself and the value of register {second_register} ({first_register_value} | {second_register_value} = {result}).")

    def opcode_set_register_bitwise_and(self, opcode: bytes) -> None:
        """
        Sets the value of the first provided register to the bitwise and of itself and the value of the second provided register.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        result = first_register_value & second_register_value
        self.registers[first_register] = result
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {first_register} to the bitwise and of itself and the value of register {second_register} ({first_register_value} & {second_register_value} = {result}).")

    def opcode_set_register_bitwise_xor(self, opcode: bytes) -> None:
        """
        Sets the value of the first provided register to the bitwise xor of itself and the value of the second provided register.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        result = first_register_value ^ second_register_value
        self.registers[first_register] = result
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {first_register} to the bitwise xor of itself and the value of register {second_register} ({first_register_value} ^ {second_register_value} = {result}).")

    def opcode_add_other_register(self, opcode: bytes) -> None:
        """
        Sets the value of the first provided register to the sum of itself and the value of the second provided register.  The carry flag (register 15) is set.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        sum_of_registers = first_register_value + second_register_value
        result = sum_of_registers % 256
        carry = 1 if sum_of_registers >= 256 else 0
        self.registers[first_register] = result
        self.registers[15] = carry
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {first_register} to the sum of itself and the value of register {second_register} ({first_register_value} + {second_register_value} = {result}, carry = {carry}).")

    def opcode_subtract_from_first_register(self, opcode: bytes) -> None:
        """
        Sets the value of the first provided register to the difference of itself and the value of the second provided register.  The not borrow flag (register 15) is set.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        result, not_borrow = self.bounded_subtract(first_register_value, second_register_value)
        self.registers[first_register] = result
        self.registers[15] = not_borrow
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {first_register} to the difference of itself and the value of register {second_register} ({first_register_value} - {second_register_value} = {result}, not borrow = {not_borrow}).")

    def opcode_bit_shift_right(self, opcode: bytes) -> None:
        """
        Shift the value of the first provided register to the right by 1.  Set register 15 to the value of the least significant bit before the operation.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        first_register_value = self.registers[first_register]
        bit_shift = first_register_value >> 1
        least_significant_bit = first_register_value & 1
        self.registers[first_register] = bit_shift
        self.registers[15] = least_significant_bit
        logger.debug(f"Execute Opcode {opcode.hex()}: Shift the value of register {first_register} to the right by 1 ({first_register_value} >> 1 = {bit_shift}, previous least significant bit = {least_significant_bit}).")

    def opcode_subtract_from_second_register(self, opcode: bytes) -> None:
        """
        Sets the value of the first provided register to the difference of the value of the second provided register and itself.  The not borrow flag (register 15) is set.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        result, not_borrow = self.bounded_subtract(second_register_value, first_register_value)
        self.registers[first_register] = result
        self.registers[15] = not_borrow
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {first_register} to the difference of the value of register {second_register} and itself ({second_register_value} - {first_register_value} = {result}, not borrow = {not_borrow}).")

    def opcode_bit_shift_left(self, opcode: bytes) -> None:
        """
        Shift the value of the first provided register to the left by 1.  Set register 15 to the value of the most significant bit before the operation.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        first_register_value = self.registers[first_register]
        bit_shift = (first_register_value << 1) & BYTE_MASK
        most_significant_bit = 1 if first_register_value & 128 == 128 else 0
        self.registers[first_register] = bit_shift
        self.registers[15] = most_significant_bit
        logger.debug(f"Execute Opcode {opcode.hex()}: Shift the value of register {first_register} to the left by 1 ({first_register_value} << 1 = {bit_shift}, previous most significant bit = {most_significant_bit}).")

    def opcode_if_register_not_equal(self, opcode: bytes) -> None:
        """
        Skip the next instruction if the value of the first provided register is not equal to the value of the second provided register.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        first_register_value = self.registers[first_register]
        second_register_value = self.registers[second_register]
        logger.debug(f"Execute Opcode {opcode.hex()}: Skip next instruction if register {first_register}'s value ({first_register_value}) is not equal to register {second_register}'s value ({second_register_value}).")
        if first_register_value != second_register_value:
            self.program_counter += 2
            logger.debug("Instruction skipped.")
        else:
            logger.debug("Instruction not skipped.")

    def opcode_set_register_i(self, opcode: bytes) -> None:
        """
        Sets the value of register I to the provided value.
        :param opcode: The opcode to execute.
        """
        address = (self.get_lower_char(opcode[0]) << 8) + opcode[1]
        self.register_i = address
        logger.debug(f"Execute Opcode {opcode.hex()}: Set register I to {hex(address)}.")

    def opcode_goto_addition(self, opcode: bytes) -> None:
        """
        Jump to the provided address plus the value of register 0.
        :param opcode: The opcode to execute.
        """
        address = (self.get_lower_char(opcode[0]) << 8) + opcode[1]
        register_value = self.registers[0]
        self.program_counter = address + register_value
        logger.debug(f"Execute Opcode {opcode.hex()}: Jump to the provided address plus the value of register 0 ({hex(address)} + {hex(register_value)} = {hex(self.program_counter)}).")

    def opcode_random_bitwise_and(self, opcode: bytes) -> None:
        """
        Set the value of the provided register to the bitwise and of the provided value and a random number [0, 255].
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        random_value = random.randint(0, 255)
        result = opcode[1] & random_value
        self.registers[register] = result
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {register} to the bitwise and of the provided value and a random number [0, 255] ({opcode[1]} & {random_value} = {result}).")

    def opcode_get_delay_timer(self, opcode: bytes) -> None:
        """
        Sets the value of the provided register to the value of the delay timer.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        self.registers[register] = self.delay
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {register} to the value of the delay timer ({self.registers[register]}).")

    def opcode_set_delay_timer(self, opcode: bytes) -> None:
        """
        Sets the delay timer to the value of the provided register.
        :param opcode: The opcode to execute.
        """
        self.toggle_delay_timer(False)
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        self.delay = register_value
        if self.delay > 0:
            self.toggle_delay_timer(True)
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of the delay timer to value of register {register} ({register_value}).")

    def opcode_set_sound_timer(self, opcode: bytes) -> None:
        """
        Sets the sound timer to the value of the provided register, playing a sound if the value is greater than 0.
        :param opcode: The opcode to execute.
        """
        self.toggle_sound_timer(False)
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        self.sound = register_value
        if self.sound > 0:
            self.sound_player.play(-1)
            self.toggle_sound_timer(True)
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of the delay timer to value of register {register} ({register_value}).")
    # endregion


if __name__ == "__main__":
    emulator = Emulator()
    emulator.game_loop()
