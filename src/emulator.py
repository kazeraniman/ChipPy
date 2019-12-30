import logging
import sys
import random
import pygame
import threading
import easygui

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
INTERPRETER_END_ADDRESS = 80
RETURN_FROM_SUBROUTINE_OPCODE = bytes.fromhex("00ee")
CLEAR_SCREEN_OPCODE = bytes.fromhex("00e0")
SCREEN_WIDTH = 64
SCREEN_HEIGHT = 32
SCALED_SCREEN_WIDTH = 800
SCALED_SCREEN_HEIGHT = 400
SPRITE_WIDTH = 8
TIMER_DELAY = 1 / 60
OPCODE_DELAY = 1 / 500
SOUND_FREQUENCY = 44100
SOUND_BUFFER = 4096
TONE_HZ = 550
GAMES_PATH = str(Path(__file__).resolve().parent.parent.joinpath("games/.chip8"))

COLOUR_PALETTE = [(0, 0, 0), (0, 255, 0)]

KEY_LOOKUP = {
    pygame.K_1: 1,
    pygame.K_q: 4,
    pygame.K_a: 7,
    pygame.K_z: 10,
    pygame.K_2: 2,
    pygame.K_w: 5,
    pygame.K_s: 8,
    pygame.K_x: 0,
    pygame.K_3: 3,
    pygame.K_e: 6,
    pygame.K_d: 9,
    pygame.K_c: 11,
    pygame.K_4: 12,
    pygame.K_r: 13,
    pygame.K_f: 14,
    pygame.K_v: 15,
}

# Initialize the random number generator
random.seed()

# Initialize PyGame
pygame.mixer.init(SOUND_FREQUENCY, -16, 1, 4096)
pygame.init()
pygame.display.init()


class WaitForKey:
    """
    A class which handles the blocking-for-key-press state.
    """
    def __init__(self):
        self.is_waiting = False
        self.storing_register = 0


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
        self.keys: List[bool] = [False] * 16
        self.screen: Optional[pygame.Surface] = None
        self.inter_screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), 0, 8)
        self.pixels = np.zeros((SCREEN_WIDTH, SCREEN_HEIGHT), np.ubyte)
        self.waiting_for_key = WaitForKey()
        self.game_loaded = False
        self.selecting_game = False

        self.opcode_timer: Optional[threading.Timer] = None
        self.delay_timer: Optional[threading.Timer] = None
        self.sound_timer: Optional[threading.Timer] = None

        self.load_digit_sprites()

        # Sound is weird; borrowing some of this chunk from here, I claim no credit for it: http://shallowsky.com/blog/programming/python-play-chords.html
        length = SOUND_FREQUENCY / TONE_HZ
        omega = np.pi * 2 / length
        x_values = np.arange(int(length)) * omega
        one_cycle = SOUND_BUFFER * np.sin(x_values)
        sound_wave = np.resize(one_cycle, (SOUND_FREQUENCY,)).astype(np.int16)
        self.sound_player = pygame.sndarray.make_sound(sound_wave)

        pygame.display.set_caption("ChipPy")
        self.screen = pygame.display.set_mode((SCALED_SCREEN_WIDTH, SCALED_SCREEN_HEIGHT), 0, 8)
        self.screen.set_palette(COLOUR_PALETTE)

    def __del__(self):
        """
        Destructor.
        """
        self.toggle_all_timers(False)

    def reset(self):
        """
        Reset the state of the emulator.
        """
        self.game_loaded = False
        self.selecting_game = False
        self.toggle_all_timers(False)
        self.sound_player.stop()
        self.waiting_for_key.is_waiting = False
        self.register_i = 0
        self.delay = 0
        self.sound = 0
        self.stack: List[int] = []
        self.keys: List[bool] = [False] * 16
        self.program_counter = GAME_START_ADDRESS
        self.pixels.fill(0)

        self.ram = bytearray(4096)
        self.registers = bytearray(16)

        self.load_digit_sprites()

        self.clear_screen()

        pygame.display.set_caption("ChipPy")

    def load_game(self) -> None:
        """
        Stop any currently running game, load the selected game into memory, and start it up.
        """
        if self.game_loaded:
            self.reset()

        self.selecting_game = True
        file_name = easygui.fileopenbox(title="Select a Game", default=GAMES_PATH, filetypes=[["*.chip8", "CHIP-8"]])
        self.selecting_game = False

        if not file_name:
            easygui.msgbox("Pick a game to play!  Press the L key to re-open the game picker.", "No Game Selected")
            return

        path = Path(file_name)

        if not path:
            easygui.msgbox("No path provided for a game to load!", "No Game Provided")
            return

        if not path.exists():
            easygui.msgbox(f"Game could not be loaded as the path does not exist!  Path: {path}.", "Game Not Found")
            return

        if path.suffix != ".chip8":
            easygui.msgbox(f"Game does not appear to be a CHIP-8 game as the '.chip8' file type was not found in the file name.  Path: {path}.", "Wrong File Extension")
            return

        logger.debug(f"Loading game at path {path}.")
        with path.open("rb") as file:
            game = file.read()
            for index, value in enumerate(game):
                self.ram[512 + index] = value

        pygame.display.set_caption(path.stem)

        self.game_loaded = True
        self.fetch_and_run_opcode()

    def load_digit_sprites(self) -> None:
        """
        Load the sprites for the hexadecimal digits 0-f into memory.
        """
        self.ram[0:5] = bytes.fromhex("f0909090f0")
        self.ram[5:10] = bytes.fromhex("2060202070")
        self.ram[10:15] = bytes.fromhex("f010f080f0")
        self.ram[15:20] = bytes.fromhex("f010f010f0")
        self.ram[20:25] = bytes.fromhex("9090f01010")
        self.ram[25:30] = bytes.fromhex("f080f010f0")
        self.ram[30:35] = bytes.fromhex("f080f090f0")
        self.ram[35:40] = bytes.fromhex("f010204040")
        self.ram[40:45] = bytes.fromhex("f090f090f0")
        self.ram[45:50] = bytes.fromhex("f090f010f0")
        self.ram[50:55] = bytes.fromhex("f090f09090")
        self.ram[55:60] = bytes.fromhex("e090e090e0")
        self.ram[60:65] = bytes.fromhex("f0808080f0")
        self.ram[65:70] = bytes.fromhex("e0909090e0")
        self.ram[70:75] = bytes.fromhex("f080f080f0")
        self.ram[75:80] = bytes.fromhex("f080f08080")

    def draw_to_display(self) -> None:
        """
        Update the display.
        """
        pygame.surfarray.blit_array(self.inter_screen, self.pixels)
        pygame.transform.scale(self.inter_screen, (SCALED_SCREEN_WIDTH, SCALED_SCREEN_HEIGHT), self.screen)
        pygame.display.flip()

    def clear_screen(self) -> None:
        """
        Clear the screen.
        """
        self.pixels.fill(0)
        self.draw_to_display()

    def print_ram(self) -> None:
        """
        Dump the full memory of the emulator.
        """
        for byte in self.ram:
            print(hex(byte))

    def event_loop(self) -> None:
        """
        Loop which handles all events and spawns the first game picker to get started.
        """
        self.load_game()

        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                    pressed = event.type == pygame.KEYDOWN

                    if pressed and event.key == pygame.K_l and not self.selecting_game:
                        self.load_game()

                    # CHIP-8 Controls
                    key = KEY_LOOKUP.get(event.key, None)
                    if key is not None:
                        self.keys[key] = pressed
                        logger.debug(f"Key State Changed.  Key: {key}, Pressed: {pressed}.")

                        if self.waiting_for_key.is_waiting and pressed:
                            self.store_key_press_in_waiting_register(key)

    def store_key_press_in_waiting_register(self, key: int) -> None:
        """
        Stores the provided key in the waiting register.
        """
        if not self.waiting_for_key.is_waiting:
            return

        self.waiting_for_key.is_waiting = False
        self.registers[self.waiting_for_key.storing_register] = key
        self.toggle_all_timers(True)
        logger.debug(f"Storing the key {key} in the register {self.waiting_for_key.storing_register}, completing the blocking opcode and un-blocking all execution.")

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

    def toggle_all_timers(self, status: bool) -> None:
        """
        Stop all timers.
        :param status: True if the timers should be started, False otherwise.
        """
        self.toggle_opcode_timer(status)
        self.toggle_delay_timer(status)
        self.toggle_sound_timer(status)

    def toggle_opcode_timer(self, status: bool) -> None:
        """
        Start / stop the opcode timer.
        :param status: True if the timer should be started, False otherwise.
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
            self.delay_timer = threading.Timer(TIMER_DELAY, self.decrement_delay_timer)
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
            self.sound_timer = threading.Timer(TIMER_DELAY, self.decrement_sound_timer)
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

        if not self.waiting_for_key.is_waiting:
            self.toggle_opcode_timer(True)

    def run_opcode(self, opcode: bytes) -> None:
        """
        Route the provided opcode to the correct method to execute it.  Increment the program counter to the next instruction.
        :param opcode: The opcode to execute.
        """
        self.program_counter += 2
        first_char = self.get_upper_char(opcode[0])
        last_char = self.get_lower_char(opcode[1])

        if opcode == CLEAR_SCREEN_OPCODE:
            self.opcode_clear_screen(opcode)
        elif opcode == RETURN_FROM_SUBROUTINE_OPCODE:
            self.opcode_return_from_subroutine(opcode)
        elif first_char == 0:
            self.opcode_call_subroutine(opcode)
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
        elif first_char == 13:
            self.opcode_draw_sprite(opcode)
        elif first_char == 14 and opcode[1] == 158:
            self.opcode_if_key_pressed(opcode)
        elif first_char == 14 and opcode[1] == 161:
            self.opcode_if_key_not_pressed(opcode)
        elif first_char == 15 and opcode[1] == 7:
            self.opcode_get_delay_timer(opcode)
        elif first_char == 15 and opcode[1] == 10:
            self.opcode_wait_for_key_press(opcode)
        elif first_char == 15 and opcode[1] == 21:
            self.opcode_set_delay_timer(opcode)
        elif first_char == 15 and opcode[1] == 24:
            self.opcode_set_sound_timer(opcode)
        elif first_char == 15 and opcode[1] == 30:
            self.opcode_register_i_addition(opcode)
        elif first_char == 15 and opcode[1] == 41:
            self.opcode_set_register_i_to_hex_sprite_address(opcode)
        elif first_char == 15 and opcode[1] == 51:
            self.opcode_binary_coded_decimal(opcode)
        elif first_char == 15 and opcode[1] == 85:
            self.opcode_register_dump(opcode)
        elif first_char == 15 and opcode[1] == 101:
            self.opcode_register_load(opcode)
        else:
            logger.error(f"Unimplemented / Invalid Opcode: {opcode.hex()}.")

    def opcode_clear_screen(self, opcode: bytes) -> None:
        """
        Clear the screen.
        :param opcode: The opcode to execute.
        """
        self.clear_screen()
        logger.debug(f"Execute Opcode {opcode.hex()}: Clearing the screen.")

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

    def opcode_draw_sprite(self, opcode: bytes) -> None:
        """
        Draws the sprite with the provided height found at the address denoted by the value of register I to the provided x and y coordinates.  The collision flag (register 15) is set to 1 if a pixel was unset, 0 otherwise.
        :param opcode: The opcode to execute.
        """
        register_x = self.get_lower_char(opcode[0])
        register_y = self.get_upper_char(opcode[1])
        register_x_value = self.registers[register_x]
        register_y_value = self.registers[register_y]
        height = self.get_lower_char(opcode[1])
        pixel_unset = 0
        for row in range(height):
            byte = self.ram[self.register_i + row]
            y_coordinate = (register_y_value + row) % SCREEN_HEIGHT
            for column in range(SPRITE_WIDTH):
                x_coordinate = (register_x_value + column) % SCREEN_WIDTH
                pixel = ((byte >> (SPRITE_WIDTH - 1 - column)) & 1)
                if pixel_unset == 0 and self.pixels[x_coordinate, y_coordinate] == 1 and pixel == 1:
                    pixel_unset = 1
                self.pixels[x_coordinate, y_coordinate] ^= pixel
        self.registers[15] = pixel_unset
        self.draw_to_display()
        logger.debug(f"Execute Opcode {opcode.hex()}: Drawing the sprite with a height of {height} and found at address {self.register_i} to the screen at the x-cooordinate from the value of register {register_x} and y-coordinate from the value of register {register_y} ({register_x_value, register_y_value}).")

    def opcode_if_key_pressed(self, opcode: bytes) -> None:
        """
        Skip the next instruction if the key represented by the value of the provided register is pressed.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        key = self.registers[register]
        pressed = self.keys[key]
        logger.debug(f"Execute Opcode {opcode.hex()}: Skip next instruction if the key represented by the value of register {register} ({key}) is pressed ({pressed}).")
        if pressed:
            self.program_counter += 2
            logger.debug("Instruction skipped.")
        else:
            logger.debug("Instruction not skipped.")

    def opcode_if_key_not_pressed(self, opcode: bytes) -> None:
        """
        Skip the next instruction if the key represented by the value of the provided register is not pressed.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        key = self.registers[register]
        pressed = self.keys[key]
        logger.debug(f"Execute Opcode {opcode.hex()}: Skip next instruction if the key represented by the value of register {register} ({key}) is not pressed ({pressed}).")
        if not pressed:
            self.program_counter += 2
            logger.debug("Instruction skipped.")
        else:
            logger.debug("Instruction not skipped.")

    def opcode_get_delay_timer(self, opcode: bytes) -> None:
        """
        Sets the value of the provided register to the value of the delay timer.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        self.registers[register] = self.delay
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register {register} to the value of the delay timer ({self.registers[register]}).")

    def opcode_wait_for_key_press(self, opcode: bytes) -> None:
        """
        Block all execution until a keypress is detected, at which point it is stored in the provided register and execution may resume.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        self.waiting_for_key.is_waiting = True
        self.waiting_for_key.storing_register = register
        logger.debug(f"Execute Opcode {opcode.hex()}: Blocking operation until a keypress is detected and stored in register {register}.")

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

    def opcode_register_i_addition(self, opcode: bytes) -> None:
        """
        Add the value of the provided register to register I.  The overflow flag (register 15) is set.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        register_i_value = self.register_i
        sum_of_registers = register_i_value + register_value
        result = sum_of_registers % 4096
        overflow = 1 if sum_of_registers >= 4096 else 0
        self.register_i = result
        self.registers[15] = overflow
        logger.debug(f"Execute Opcode {opcode.hex()}: Adds the value of register {register} to the value of register I {register} ({register_i_value} + {register_value} = {result}, overflow = {overflow}).")

    def opcode_set_register_i_to_hex_sprite_address(self, opcode: bytes) -> None:
        """
        Sets the value of register I to the address of the hexadecimal sprite represented by the value in the provided register.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        self.register_i = register_value * 5
        logger.debug(f"Execute Opcode {opcode.hex()}: Set the value of register I to the address ({self.register_i}) of the hexadecimal sprite represented by the value of register {register} ({register_value}).")

    def opcode_binary_coded_decimal(self, opcode: bytes) -> None:
        """
        Store the Binary Coded Decimal representation of the value of the provided register in memory, starting at the value of register I.
        Hundreds digit stored in memory at the location of the value of register I.
        Tens digit stored in memory at the location of the value of register I + 1.
        Units digit stored in memory at the location of the value of register I + 2.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        hundreds = register_value // 100 % 10
        tens = register_value // 10 % 10
        units = register_value % 10
        self.ram[self.register_i] = hundreds
        self.ram[self.register_i + 1] = tens
        self.ram[self.register_i + 2] = units
        logger.debug(f"Execute Opcode {opcode.hex()}: Store the Binary Coded Decimal representation of the value of register {register} ({register_value}), starting at the value of register I ({hex(self.register_i)}), ({hundreds} at {hex(self.register_i)}, {tens} at {hex(self.register_i + 1)}, {units} at {hex(self.register_i + 2)}).")

    def opcode_register_dump(self, opcode: bytes) -> None:
        """
        Store the values of all registers from register 0 to the provided register in memory, starting at the value of register I.
        :param opcode: The opcode to execute.
        """
        last_register = self.get_lower_char(opcode[0])
        logger.debug(f"Execute Opcode {opcode.hex()}: Dumping the values of all registers from register 0 to register {last_register} into memory, starting at the value of register I ({hex(self.register_i)}).")
        for register in range(last_register + 1):
            target_address = self.register_i + register
            register_value = self.registers[register]
            self.ram[target_address] = register_value
            logger.debug(f"Register {register}'s value ({register_value}) stored at address {target_address}.")

    def opcode_register_load(self, opcode: bytes) -> None:
        """
        Load the values of all registers from register 0 to the provided register from memory, starting at the value of register I.
        :param opcode: The opcode to execute.
        """
        last_register = self.get_lower_char(opcode[0])
        logger.debug(f"Execute Opcode {opcode.hex()}: Loading the values of all registers from register 0 to register {last_register} from memory, starting at the value of register I ({hex(self.register_i)}).")
        for register in range(last_register + 1):
            target_address = self.register_i + register
            self.registers[register] = self.ram[target_address]
            logger.debug(f"Register {register}'s value ({self.registers[register]}) loaded from address {target_address}.")
    # endregion


if __name__ == "__main__":
    emulator = Emulator()
    emulator.event_loop()
