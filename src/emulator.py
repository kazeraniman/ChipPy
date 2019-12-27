import logging
import sys

from typing import List

from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s]:  %(message)s", stream=sys.stdout)
logger.disabled = "pydevd" not in sys.modules

UPPER_CHAR_MASK = 240
LOWER_CHAR_MASK = 15
GAME_START_ADDRESS = 512
RETURN_FROM_SUBROUTINE_OPCODE = bytes.fromhex("00EE")


class Emulator:
    def __init__(self):
        self.ram = bytearray(4096)
        self.registers = bytearray(16)
        self.program_counter = GAME_START_ADDRESS
        self.stack: List[int] = []

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
    # endregion

    # region Opcodes
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
        logger.debug(f"Execute Opcode {opcode.hex}: Return from subroutine, continue at {hex(self.program_counter)}.")

    def opcode_goto(self, opcode: bytes) -> None:
        """
        Jump to the provided address.
        :param opcode: The opcode to execute.
        """
        address = (self.get_lower_char(opcode[0]) << 8) + opcode[1]
        self.program_counter = address
        logger.debug(f"Execute Opcode {opcode.hex}: Jump to address {hex(address)}.")

    def opcode_call_subroutine(self, opcode: bytes) -> None:
        """
        Call the subroutine at the given address.
        :param opcode: The opcode to execute.
        """
        address = (self.get_lower_char(opcode[0]) << 8) + opcode[1]
        self.stack.append(self.program_counter)
        self.program_counter = address
        logger.debug(f"Execute Opcode {opcode.hex}: Call subroutine at address {hex(address)}.")

    def opcode_if_equal(self, opcode: bytes) -> None:
        """
        Skip the next instruction if the value of the provided register is equal to the provided value.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        register_value = self.registers[register]
        logger.debug(f"Execute Opcode {opcode.hex}: Skip next instruction if register {register}'s value ({register_value}) is {opcode[1]}.")
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
        logger.debug(f"Execute Opcode {opcode.hex}: Skip next instruction if register {register}'s value ({register_value}) is not {opcode[1]}.")
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
        logger.debug(f"Execute Opcode {opcode.hex}: Skip next instruction if register {first_register}'s value ({first_register_value}) is equal to register {second_register}'s value ({second_register_value}).")
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
        logger.debug(f"Execute Opcode {opcode.hex}: Set the value of register {register} to {opcode[1]}.")

    def opcode_add_value(self, opcode: bytes) -> None:
        """
        Adds the provided value to the value of the provided register.  The carry flag is not set.
        :param opcode: The opcode to execute.
        """
        register = self.get_lower_char(opcode[0])
        self.registers[register] = (self.registers[register] + opcode[1]) % 256
        logger.debug(f"Execute Opcode {opcode.hex}: Add {opcode[1]} to the value of register {register}.")

    def opcode_set_register_value_other_register(self, opcode: bytes) -> None:
        """
        Set the value of the first provided register to the value of the second provided register.
        :param opcode: The opcode to execute.
        """
        first_register = self.get_lower_char(opcode[0])
        second_register = self.get_upper_char(opcode[1])
        second_register_value = self.registers[second_register]
        self.registers[first_register] = second_register_value
        logger.debug(f"Execute Opcode {opcode.hex}: Set the value of register {first_register} to the value of register {second_register}'s value ({second_register_value}).")

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
        logger.debug(f"Execute Opcode {opcode.hex}: Set the value of register {first_register} to the bitwise or of itself and the value of register {second_register} ({first_register_value} | {second_register_value} = {result}).")

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
        logger.debug(f"Execute Opcode {opcode.hex}: Set the value of register {first_register} to the bitwise and of itself and the value of register {second_register} ({first_register_value} & {second_register_value} = {result}).")

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
        logger.debug(f"Execute Opcode {opcode.hex}: Set the value of register {first_register} to the bitwise xor of itself and the value of register {second_register} ({first_register_value} ^ {second_register_value} = {result}).")
    # endregion
