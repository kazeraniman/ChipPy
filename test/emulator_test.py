from unittest import mock

from src.emulator import Emulator, GAME_START_ADDRESS, INTERPRETER_END_ADDRESS


class TestHelperMethods:
    def setup_method(self):
        self.emulator = Emulator()

    def test_load_digit_sprites(self):
        self.emulator.ram = bytearray(4096)

        self.emulator.load_digit_sprites()
        for index, byte in enumerate(self.emulator.ram):
            if index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Ram outside of the sprite storage was modified."
        assert self.emulator.ram[0] == int("f0", 16), "The first character of the 0 sprite is incorrect."
        assert self.emulator.ram[1] == int("90", 16), "The second character of the 0 sprite is incorrect."
        assert self.emulator.ram[2] == int("90", 16), "The third character of the 0 sprite is incorrect."
        assert self.emulator.ram[3] == int("90", 16), "The fourth character of the 0 sprite is incorrect."
        assert self.emulator.ram[4] == int("f0", 16), "The fifth character of the 0 sprite is incorrect."
        assert self.emulator.ram[35] == int("f0", 16), "The first character of the 7 sprite is incorrect."
        assert self.emulator.ram[36] == int("10", 16), "The second character of the 7 sprite is incorrect."
        assert self.emulator.ram[37] == int("20", 16), "The third character of the 7 sprite is incorrect."
        assert self.emulator.ram[38] == int("40", 16), "The fourth character of the 7 sprite is incorrect."
        assert self.emulator.ram[39] == int("40", 16), "The fifth character of the 7 sprite is incorrect."
        assert self.emulator.ram[75] == int("f0", 16), "The first character of the F sprite is incorrect."
        assert self.emulator.ram[76] == int("80", 16), "The second character of the F sprite is incorrect."
        assert self.emulator.ram[77] == int("f0", 16), "The third character of the F sprite is incorrect."
        assert self.emulator.ram[78] == int("80", 16), "The fourth character of the F sprite is incorrect."
        assert self.emulator.ram[79] == int("80", 16), "The fifth character of the F sprite is incorrect."


class TestIndividualOpcodes:
    def setup_method(self):
        self.emulator = Emulator()

    def test_opcode_return_from_subroutine(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert len(self.emulator.stack) == 0, "Stack starting out non-empty."

        self.emulator.opcode_return_from_subroutine(bytes.fromhex("00EE"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Returning from a subroutine when not in one messed up the program counter."
        assert len(self.emulator.stack) == 0, "Stack got into a weird state when trying to return from a subroutine when not in one."

        self.emulator.stack = [2000, 3000]
        self.emulator.opcode_return_from_subroutine(bytes.fromhex("00EE"))
        assert self.emulator.program_counter == 3000, "Program counter set to wrong value when returning from a subroutine."
        assert len(self.emulator.stack) == 1, "Stack entries incorrect after returning from a subroutine."

        self.emulator.opcode_return_from_subroutine(bytes.fromhex("00EE"))
        assert self.emulator.program_counter == 2000, "Program counter set to wrong value when returning from a subroutine."
        assert len(self.emulator.stack) == 0, "Stack entries incorrect after returning from a subroutine."

    def test_opcode_goto(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.opcode_goto(bytes.fromhex("14e5"))
        assert self.emulator.program_counter == int("4e5", 16), "Program counter incorrect after jump opcode."

    def test_opcode_call_subroutine(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert len(self.emulator.stack) == 0, "Stack starting out non-empty."

        self.emulator.opcode_call_subroutine(bytes.fromhex("2578"))
        assert self.emulator.program_counter == int("578", 16), "Program counter incorrect after subroutine call."
        assert len(self.emulator.stack) == 1 and self.emulator.stack[0] == GAME_START_ADDRESS, "Previous program counter not added to the stack."

        self.emulator.opcode_call_subroutine(bytes.fromhex("2a23"))
        assert self.emulator.program_counter == int("a23", 16), "Program counter incorrect after subroutine call."
        assert len(self.emulator.stack) == 2 and self.emulator.stack[1] == int("578", 16), "Previous program counter not added to the stack."
        assert len(self.emulator.stack) == 2 and self.emulator.stack[0] == GAME_START_ADDRESS, "Earlier stack value was modified."

    def test_opcode_if_equal(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert self.emulator.registers[6] == 0, "Register starting at an unexpected value."

        self.emulator.opcode_if_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite register value not matching."

        self.emulator.registers[6] = int("98", 16)
        self.emulator.opcode_if_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_if_not_equal(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.registers[6] = int("98", 16)
        self.emulator.opcode_if_not_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite register value matching."

        self.emulator.registers[6] = int("ff", 16)
        self.emulator.opcode_if_not_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_if_register_equal(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.registers[10] = int("11", 16)
        self.emulator.registers[4] = int("12", 16)
        self.emulator.opcode_if_register_equal(bytes.fromhex("5a40"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite register values matching."

        self.emulator.registers[10] = int("40", 16)
        self.emulator.registers[4] = int("40", 16)
        self.emulator.opcode_if_register_equal(bytes.fromhex("5a40"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_set_register_value(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.opcode_set_register_value(bytes.fromhex("6133"))
        for index, register in enumerate(self.emulator.registers):
            if index == 1:
                assert register == int("33", 16), "Register not set to correct value."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_add_value(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[11] = 10
        self.emulator.opcode_add_value(bytes.fromhex("7b05"))
        for index, register in enumerate(self.emulator.registers):
            if index == 11:
                assert register == 15, "Register addition failed."
            else:
                assert register == 0, "Different register than target had its value modified."

        self.emulator.opcode_add_value(bytes.fromhex("7bfa"))
        assert self.emulator.registers[11] == 9, "Register addition overflow did not work as expected."
        assert self.emulator.registers[15] == 0, "Carry bit was set when it should not be modified by this instruction."

    def test_opcode_set_register_value_other_register(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[8] = 47
        self.emulator.opcode_set_register_value_other_register(bytes.fromhex("8480"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4 or index == 8:
                assert register == 47, "Register not set to correct value."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_set_register_bitwise_or(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 170
        self.emulator.registers[8] = 85
        self.emulator.opcode_set_register_bitwise_or(bytes.fromhex("8481"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 255, "Register not set to correct value."
            elif index == 8:
                assert register == 85, "Second register value was modified when it should not have been."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_set_register_bitwise_and(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 204
        self.emulator.registers[8] = 170
        self.emulator.opcode_set_register_bitwise_and(bytes.fromhex("8482"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 136, "Register not set to correct value."
            elif index == 8:
                assert register == 170, "Second register value was modified when it should not have been."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_set_register_bitwise_xor(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 204
        self.emulator.registers[8] = 170
        self.emulator.opcode_set_register_bitwise_xor(bytes.fromhex("8483"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 102, "Register not set to correct value."
            elif index == 8:
                assert register == 170, "Second register value was modified when it should not have been."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_add_other_register(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 200
        self.emulator.registers[8] = 33
        self.emulator.opcode_add_other_register(bytes.fromhex("8484"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 233, "Register not set to correct value."
            elif index == 8:
                assert register == 33, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 0, "Carry flag was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

        self.emulator.opcode_add_other_register(bytes.fromhex("8484"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 10, "Register not set to correct value."
            elif index == 8:
                assert register == 33, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 1, "Carry flag was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_subtract_from_first_register(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 100
        self.emulator.registers[8] = 70
        self.emulator.opcode_subtract_from_first_register(bytes.fromhex("8485"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 30, "Register not set to correct value."
            elif index == 8:
                assert register == 70, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 1, "Not borrow flag was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

        self.emulator.opcode_subtract_from_first_register(bytes.fromhex("8485"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 216, "Register not set to correct value."
            elif index == 8:
                assert register == 70, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 0, "Not borrow flag was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_bit_shift_right(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 85
        self.emulator.registers[8] = 70
        self.emulator.opcode_bit_shift_right(bytes.fromhex("8486"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 42, "Register not set to correct value."
            elif index == 8:
                assert register == 70, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 1, "Least significant bit was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

        self.emulator.opcode_bit_shift_right(bytes.fromhex("8486"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 21, "Register not set to correct value."
            elif index == 8:
                assert register == 70, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 0, "Least significant bit was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_subtract_from_second_register(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 70
        self.emulator.registers[8] = 100
        self.emulator.opcode_subtract_from_second_register(bytes.fromhex("8487"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 30, "Register not set to correct value."
            elif index == 8:
                assert register == 100, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 1, "Not borrow flag was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

        self.emulator.registers[8] = 10
        self.emulator.opcode_subtract_from_second_register(bytes.fromhex("8487"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 236, "Register not set to correct value."
            elif index == 8:
                assert register == 10, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 0, "Not borrow flag was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_bit_shift_left(self):
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.registers[4] = 171
        self.emulator.registers[8] = 70
        self.emulator.opcode_bit_shift_left(bytes.fromhex("848e"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 86, "Register not set to correct value."
            elif index == 8:
                assert register == 70, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 1, "Most significant bit was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

        self.emulator.opcode_bit_shift_left(bytes.fromhex("848e"))
        for index, register in enumerate(self.emulator.registers):
            if index == 4:
                assert register == 172, "Register not set to correct value."
            elif index == 8:
                assert register == 70, "Second register value was modified when it should not have been."
            elif index == 15:
                assert register == 0, "Most significant bit was set incorrectly."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_if_register_not_equal(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.registers[10] = int("40", 16)
        self.emulator.registers[4] = int("40", 16)
        self.emulator.opcode_if_register_not_equal(bytes.fromhex("9a40"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite register values not matching."

        self.emulator.registers[10] = int("11", 16)
        self.emulator.registers[4] = int("12", 16)
        self.emulator.opcode_if_register_not_equal(bytes.fromhex("9a40"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_set_register_i(self):
        assert self.emulator.register_i == 0, "Register I starting at an unexpected value."

        self.emulator.opcode_set_register_i(bytes.fromhex("a491"))
        assert self.emulator.register_i == int("491", 16), "Register I set to the wrong value."

    def test_opcode_goto_addition(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."

        self.emulator.registers[0] = 20
        self.emulator.opcode_goto_addition(bytes.fromhex("b5b2"))
        assert self.emulator.program_counter == int("5b2", 16) + 20, "Program counter incorrect after jump opcode."

    def test_opcode_if_key_pressed(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert not self.emulator.keys[6], "Key press starting at an unexpected value."

        self.emulator.opcode_if_key_pressed(bytes.fromhex("e69e"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite key not pressed."

        self.emulator.keys[6] = True
        self.emulator.opcode_if_key_pressed(bytes.fromhex("e69e"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_if_key_not_pressed(self):
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter starting at an unexpected value."
        assert not self.emulator.keys[6], "Key press starting at an unexpected value."

        self.emulator.keys[6] = True
        self.emulator.opcode_if_key_not_pressed(bytes.fromhex("e6a1"))
        assert self.emulator.program_counter == GAME_START_ADDRESS, "Program counter was changed despite key pressed."

        self.emulator.keys[6] = False
        self.emulator.opcode_if_key_not_pressed(bytes.fromhex("e6a1"))
        assert self.emulator.program_counter == GAME_START_ADDRESS + 2, "Next instruction was not skipped when it should have been."

    def test_opcode_get_delay_timer(self):
        assert self.emulator.delay == 0, "Delay timer starting at an unexpected value."
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        self.emulator.delay = 55
        self.emulator.opcode_get_delay_timer(bytes.fromhex("f307"))
        for index, register in enumerate(self.emulator.registers):
            if index == 3:
                assert register == 55, "Register not set to correct value."
            else:
                assert register == 0, "Different register than target had its value modified."

    def test_opcode_set_delay_timer(self):
        assert self.emulator.delay == 0, "Delay timer starting at an unexpected value."

        self.emulator.registers[3] = 44
        self.emulator.opcode_set_delay_timer(bytes.fromhex("f315"))
        assert self.emulator.delay == 44, "Delay timer was not set correctly."

    def test_opcode_set_sound_timer(self):
        assert self.emulator.sound == 0, "Sound timer starting at an unexpected value."

        self.emulator.registers[3] = 44
        self.emulator.opcode_set_sound_timer(bytes.fromhex("f318"))
        assert self.emulator.sound == 44, "Sound timer was not set correctly."

    def test_opcode_register_i_addition(self):
        self.emulator.register_i = 4050
        self.emulator.registers[7] = 50
        self.emulator.opcode_register_i_addition(bytes.fromhex("f71e"))
        assert self.emulator.register_i == 4, "Register I set to the wrong value."
        assert self.emulator.registers[7] == 50, "Value of register was changed when it was not the target of the addition."
        assert self.emulator.registers[15] == 1, "Overflow flag was not set correctly."

        self.emulator.opcode_register_i_addition(bytes.fromhex("f71e"))
        assert self.emulator.register_i == 54, "Register I set to the wrong value."
        assert self.emulator.registers[7] == 50, "Value of register was changed when it was not the target of the addition."
        assert self.emulator.registers[15] == 0, "Overflow flag was not set correctly."

    def test_opcode_set_register_i_to_hex_sprite_address(self):
        assert self.emulator.register_i == 0

        self.emulator.load_digit_sprites()
        self.emulator.registers[4] = 11
        self.emulator.opcode_set_register_i_to_hex_sprite_address(bytes.fromhex("f429"))
        assert self.emulator.register_i == 55, "Register I was not set to the correct address for the given sprite."
        assert self.emulator.ram[self.emulator.register_i] == int("e0", 16), "The first character of the B sprite is incorrect."
        assert self.emulator.ram[self.emulator.register_i + 1] == int("90", 16), "The second character of the B sprite is incorrect."
        assert self.emulator.ram[self.emulator.register_i + 2] == int("e0", 16), "The third character of the B sprite is incorrect."
        assert self.emulator.ram[self.emulator.register_i + 3] == int("90", 16), "The fourth character of the B sprite is incorrect."
        assert self.emulator.ram[self.emulator.register_i + 4] == int("e0", 16), "The fifth character of the B sprite is incorrect."

    def test_opcode_binary_coded_decimal(self):
        for index, byte in enumerate(self.emulator.ram):
            if index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Ram starting at an unexpected value."

        self.emulator.register_i = 3123
        self.emulator.registers[12] = 135
        self.emulator.opcode_binary_coded_decimal(bytes.fromhex("fc33"))
        assert self.emulator.register_i == 3123, "Register I was modified when it should be left untouched."
        for index, byte in enumerate(self.emulator.ram):
            if index == 3123:
                assert byte == 1, "Hundreds digit set to the incorrect value."
            elif index == 3124:
                assert byte == 3, "Tens digit set to the incorrect value."
            elif index == 3125:
                assert byte == 5, "Units digit set to the incorrect value."
            elif index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Non-targeted ram address was changed when it shouldn't have been."

        self.emulator.registers[12] = 68
        self.emulator.opcode_binary_coded_decimal(bytes.fromhex("fc33"))
        assert self.emulator.register_i == 3123, "Register I was modified when it should be left untouched."
        for index, byte in enumerate(self.emulator.ram):
            if index == 3123:
                assert byte == 0, "Hundreds digit set to the incorrect value."
            elif index == 3124:
                assert byte == 6, "Tens digit set to the incorrect value."
            elif index == 3125:
                assert byte == 8, "Units digit set to the incorrect value."
            elif index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Non-targeted ram address was changed when it shouldn't have been."

        self.emulator.registers[12] = 5
        self.emulator.opcode_binary_coded_decimal(bytes.fromhex("fc33"))
        assert self.emulator.register_i == 3123, "Register I was modified when it should be left untouched."
        for index, byte in enumerate(self.emulator.ram):
            if index == 3123:
                assert byte == 0, "Hundreds digit set to the incorrect value."
            elif index == 3124:
                assert byte == 0, "Tens digit set to the incorrect value."
            elif index == 3125:
                assert byte == 5, "Units digit set to the incorrect value."
            elif index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Non-targeted ram address was changed when it shouldn't have been."

    def test_opcode_register_dump(self):
        for index, byte in enumerate(self.emulator.ram):
            if index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Ram starting at an unexpected value."
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        last_register = 12
        self.emulator.register_i = 2000
        for register in range(last_register + 1):
            self.emulator.registers[register] = (register + 1) * 10
        self.emulator.opcode_register_dump(bytes.fromhex("fc55"))
        assert self.emulator.register_i == 2000, "Register I was modified when it should be left untouched."
        for index, register in enumerate(self.emulator.registers):
            if index < last_register + 1:
                assert register == (index + 1) * 10, "Register value was modified by dump."
            else:
                assert register == 0, "Non-targeted register was modified."
        for index, byte in enumerate(self.emulator.ram):
            if self.emulator.register_i <= index <= self.emulator.register_i + last_register:
                assert byte == (index - self.emulator.register_i + 1) * 10, "Register was not dumped correctly."
            elif index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Non-targeted memory address was modified."

    def test_opcode_register_load(self):
        for index, byte in enumerate(self.emulator.ram):
            if index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Ram starting at an unexpected value."
        for register in self.emulator.registers:
            assert register == 0, "Register starting at an unexpected value."

        last_register = 12
        self.emulator.register_i = 2000
        for byte in range(last_register + 1):
            self.emulator.ram[self.emulator.register_i + byte] = (byte + 1) * 10
        self.emulator.opcode_register_load(bytes.fromhex("fc65"))
        assert self.emulator.register_i == 2000, "Register I was modified when it should be left untouched."
        for index, register in enumerate(self.emulator.registers):
            if index < last_register + 1:
                assert register == (index + 1) * 10, "Register value was not loaded correctly"
            else:
                assert register == 0, "Non-targeted register was modified."
        for index, byte in enumerate(self.emulator.ram):
            if self.emulator.register_i <= index <= self.emulator.register_i + last_register:
                assert byte == (index - self.emulator.register_i + 1) * 10, "Ram was modified by the load."
            elif index >= INTERPRETER_END_ADDRESS:
                assert byte == 0, "Non-targeted memory address was modified."


class TestOpcodeRouting:
    @classmethod
    def setup_class(cls):
        cls.emulator = Emulator()

    def run_opcode(self, opcode: bytes, bad_opcode: bytes, mock_method: mock.patch.object):
        self.emulator.run_opcode(bad_opcode)
        mock_method.assert_not_called()

        self.emulator.run_opcode(opcode)
        mock_method.assert_called_with(opcode)

    @mock.patch.object(Emulator, "opcode_call_subroutine")
    def test_call_machine_code_routine(self, mock_method):
        opcode = bytes.fromhex("0d52")
        bad_opcode = bytes.fromhex("00ee")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_clear_screen")
    def test_clear_screen(self, mock_method):
        opcode = bytes.fromhex("00e0")
        bad_opcode = bytes.fromhex("00ee")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_return_from_subroutine")
    def test_return_from_subroutine(self, mock_method):
        opcode = bytes.fromhex("00ee")
        bad_opcode = bytes.fromhex("00e0")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_goto")
    def test_goto(self, mock_method):
        opcode = bytes.fromhex("132a")
        bad_opcode = bytes.fromhex("332a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_call_subroutine")
    def test_call_subroutine(self, mock_method):
        opcode = bytes.fromhex("232a")
        bad_opcode = bytes.fromhex("332a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_equal")
    def test_if_equal(self, mock_method):
        opcode = bytes.fromhex("332a")
        bad_opcode = bytes.fromhex("132a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_not_equal")
    def test_if_not_equal(self, mock_method):
        opcode = bytes.fromhex("432a")
        bad_opcode = bytes.fromhex("132a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_register_equal")
    def test_if_register_equal(self, mock_method):
        opcode = bytes.fromhex("5320")
        bad_opcode = bytes.fromhex("9320")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_value")
    def test_set_register_value(self, mock_method):
        opcode = bytes.fromhex("6133")
        bad_opcode = bytes.fromhex("5321")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_add_value")
    def test_add_value(self, mock_method):
        opcode = bytes.fromhex("7433")
        bad_opcode = bytes.fromhex("6133")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_return_from_subroutine")
    def test_return_from_subroutine(self, mock_method):
        opcode = bytes.fromhex("00EE")
        bad_opcode = bytes.fromhex("7433")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_value_other_register")
    def test_set_register_value_other_register(self, mock_method):
        opcode = bytes.fromhex("8480")
        bad_opcode = bytes.fromhex("00EE")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_bitwise_or")
    def test_set_register_bitwise_or(self, mock_method):
        opcode = bytes.fromhex("8481")
        bad_opcode = bytes.fromhex("8480")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_bitwise_and")
    def test_set_register_bitwise_and(self, mock_method):
        opcode = bytes.fromhex("8482")
        bad_opcode = bytes.fromhex("8481")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_bitwise_xor")
    def test_set_register_bitwise_xor(self, mock_method):
        opcode = bytes.fromhex("8483")
        bad_opcode = bytes.fromhex("8482")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_add_other_register")
    def test_add_other_register(self, mock_method):
        opcode = bytes.fromhex("8484")
        bad_opcode = bytes.fromhex("8483")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_subtract_from_first_register")
    def test_subtract_from_first_register(self, mock_method):
        opcode = bytes.fromhex("8485")
        bad_opcode = bytes.fromhex("8484")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_bit_shift_right")
    def test_bit_shift_right(self, mock_method):
        opcode = bytes.fromhex("8486")
        bad_opcode = bytes.fromhex("848e")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_subtract_from_second_register")
    def test_subtract_from_second_register(self, mock_method):
        opcode = bytes.fromhex("8487")
        bad_opcode = bytes.fromhex("8485")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_bit_shift_left")
    def test_bit_shift_left(self, mock_method):
        opcode = bytes.fromhex("848e")
        bad_opcode = bytes.fromhex("8486")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_register_not_equal")
    def test_if_register_not_equal(self, mock_method):
        opcode = bytes.fromhex("9320")
        bad_opcode = bytes.fromhex("5320")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_i")
    def test_set_register_i(self, mock_method):
        opcode = bytes.fromhex("a841")
        bad_opcode = bytes.fromhex("9320")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_goto_addition")
    def test_goto_addition(self, mock_method):
        opcode = bytes.fromhex("b5b2")
        bad_opcode = bytes.fromhex("a841")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_random_bitwise_and")
    def test_random_bitwise_and(self, mock_method):
        opcode = bytes.fromhex("c499")
        bad_opcode = bytes.fromhex("b5b2")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_draw_sprite")
    def test_draw_sprite(self, mock_method):
        opcode = bytes.fromhex("d458")
        bad_opcode = bytes.fromhex("c499")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_key_pressed")
    def test_if_key_pressed(self, mock_method):
        opcode = bytes.fromhex("e49e")
        bad_opcode = bytes.fromhex("e4a1")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_key_not_pressed")
    def test_if_key_not_pressed(self, mock_method):
        opcode = bytes.fromhex("e4a1")
        bad_opcode = bytes.fromhex("e49e")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_get_delay_timer")
    def test_get_delay_timer(self, mock_method):
        opcode = bytes.fromhex("f307")
        bad_opcode = bytes.fromhex("c499")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_wait_for_key_press")
    def test_wait_for_key_press(self, mock_method):
        opcode = bytes.fromhex("f90a")
        bad_opcode = bytes.fromhex("f307")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_delay_timer")
    def test_set_delay_timer(self, mock_method):
        opcode = bytes.fromhex("f315")
        bad_opcode = bytes.fromhex("c499")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_sound_timer")
    def test_set_sound_timer(self, mock_method):
        opcode = bytes.fromhex("f318")
        bad_opcode = bytes.fromhex("f315")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_register_i_addition")
    def test_register_i_addition(self, mock_method):
        opcode = bytes.fromhex("f71e")
        bad_opcode = bytes.fromhex("f318")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_set_register_i_to_hex_sprite_address")
    def test_set_register_i_to_hex_sprite_address(self, mock_method):
        opcode = bytes.fromhex("f029")
        bad_opcode = bytes.fromhex("f71e")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_binary_coded_decimal")
    def test_binary_coded_decimal(self, mock_method):
        opcode = bytes.fromhex("fc33")
        bad_opcode = bytes.fromhex("f71e")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_register_dump")
    def test_register_dump(self, mock_method):
        opcode = bytes.fromhex("fc55")
        bad_opcode = bytes.fromhex("fc65")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_register_load")
    def test_register_load(self, mock_method):
        opcode = bytes.fromhex("fc65")
        bad_opcode = bytes.fromhex("fc55")
        self.run_opcode(opcode, bad_opcode, mock_method)
