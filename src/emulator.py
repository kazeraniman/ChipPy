import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s]:  %(message)s", stream=sys.stdout)
logger.disabled = "pydevd" not in sys.modules

UPPER_CHAR_MASK = 240
LOWER_CHAR_MASK = 15


class Emulator:
    def __init__(self):
        self.registers = bytearray(16)
        self.program_counter = 0

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

        if first_char == 1:
            self.opcode_goto(opcode)
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
        else:
            logger.error(f"Unimplemented / Invalid Opcode: {opcode.hex()}.")

    def opcode_goto(self, opcode: bytes) -> None:
        """
        Jump to the provided address.
        :param opcode: The opcode to execute.
        """
        address = (self.get_lower_char(opcode[0]) << 8) + opcode[1]
        self.program_counter = address
        logger.debug(f"Execute Opcode {opcode.hex}: Jump to address {hex(address)}")

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
    # endregion
